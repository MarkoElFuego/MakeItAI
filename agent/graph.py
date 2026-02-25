"""
MakeItAi – LangGraph Orchestrator (Phase 2)

4 nodes: SCOUT, MASTER, TROUBLESHOOTER, MERCHANT
Router decides which node handles each user message.
MASTER node uses the existing RAG pipeline.
"""

import os
import sys
from pathlib import Path
from typing import Literal

import anthropic
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from supabase import create_client
from typing_extensions import TypedDict

# ── Setup ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from prompts.system_prompts import (
    SYSTEM_PROMPT_MERCHANT,
    SYSTEM_PROMPT_RAG,
    SYSTEM_PROMPT_ROUTER,
    SYSTEM_PROMPT_SCOUT,
    SYSTEM_PROMPT_VISION,
)

# ── Clients ──────────────────────────────────────────────────────────────────
claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
supabase_client = create_client(
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
)
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_query",
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

ROUTER_MODEL = "claude-haiku-4-5-20251001"
NODE_MODEL = "claude-haiku-4-5-20251001"

Phase = Literal["SCOUT", "MASTER", "TROUBLESHOOTER", "MERCHANT"]


# ── State ────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    user_message: str
    current_phase: Phase
    project_context: dict          # material, tool, product, budget …
    conversation_history: list     # [{role, content}, …]
    response: str
    sources: list


# ── Helper: RAG retrieval ────────────────────────────────────────────────────
def _rag_retrieve(question: str, top_k: int = 5) -> tuple[str, list[dict]]:
    """Embed question, search Supabase, return (context_str, sources)."""
    query_embedding = embeddings.embed_query(question)
    result = supabase_client.rpc(
        "match_documents",
        {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": top_k,
        },
    ).execute()

    documents = result.data or []
    context_parts = []
    sources = []
    for doc in documents:
        context_parts.append(doc["content"])
        sources.append({
            "content": doc["content"][:200] + "...",
            "similarity": doc["similarity"],
            "metadata": doc.get("metadata", {}),
        })
    context = "\n\n---\n\n".join(context_parts) if context_parts else ""
    return context, sources


# ── Helper: call Claude ──────────────────────────────────────────────────────
def _call_claude(system: str, messages: list[dict], model: str = NODE_MODEL) -> str:
    resp = claude.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return resp.content[0].text


# ── Router ───────────────────────────────────────────────────────────────────
def route_message(state: AgentState) -> Phase:
    """Use Claude to classify the user message into a phase."""
    phase = _call_claude(
        system=SYSTEM_PROMPT_ROUTER,
        messages=[{"role": "user", "content": state["user_message"]}],
        model=ROUTER_MODEL,
    ).strip().upper()

    valid = {"SCOUT", "MASTER", "TROUBLESHOOTER", "MERCHANT"}
    return phase if phase in valid else "MASTER"


# ── Node: SCOUT ──────────────────────────────────────────────────────────────
def scout_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    messages = history + [{"role": "user", "content": state["user_message"]}]
    answer = _call_claude(system=SYSTEM_PROMPT_SCOUT, messages=messages)
    return {
        "current_phase": "SCOUT",
        "response": answer,
        "sources": [],
        "conversation_history": messages + [{"role": "assistant", "content": answer}],
    }


# ── Node: MASTER (uses RAG) ─────────────────────────────────────────────────
def master_node(state: AgentState) -> dict:
    context, sources = _rag_retrieve(state["user_message"])

    if context:
        user_content = (
            f"Kontekst iz knjiga:\n\n{context}\n\n---\n\nPitanje: {state['user_message']}"
        )
    else:
        user_content = state["user_message"]

    history = state.get("conversation_history", [])
    messages = history + [{"role": "user", "content": user_content}]
    answer = _call_claude(system=SYSTEM_PROMPT_RAG, messages=messages)

    # Keep clean user message in history (without RAG context)
    clean_history = history + [
        {"role": "user", "content": state["user_message"]},
        {"role": "assistant", "content": answer},
    ]
    return {
        "current_phase": "MASTER",
        "response": answer,
        "sources": sources,
        "conversation_history": clean_history,
    }


# ── Node: TROUBLESHOOTER ────────────────────────────────────────────────────
def troubleshooter_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    messages = history + [{"role": "user", "content": state["user_message"]}]
    answer = _call_claude(system=SYSTEM_PROMPT_VISION, messages=messages)
    return {
        "current_phase": "TROUBLESHOOTER",
        "response": answer,
        "sources": [],
        "conversation_history": messages + [{"role": "assistant", "content": answer}],
    }


# ── Node: MERCHANT ───────────────────────────────────────────────────────────
def merchant_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    messages = history + [{"role": "user", "content": state["user_message"]}]
    answer = _call_claude(system=SYSTEM_PROMPT_MERCHANT, messages=messages)
    return {
        "current_phase": "MERCHANT",
        "response": answer,
        "sources": [],
        "conversation_history": messages + [{"role": "assistant", "content": answer}],
    }


# ── Build graph ──────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("scout", scout_node)
    graph.add_node("master", master_node)
    graph.add_node("troubleshooter", troubleshooter_node)
    graph.add_node("merchant", merchant_node)

    # Entry: conditional routing based on user message
    graph.set_conditional_entry_point(
        route_message,
        {
            "SCOUT": "scout",
            "MASTER": "master",
            "TROUBLESHOOTER": "troubleshooter",
            "MERCHANT": "merchant",
        },
    )

    # Each node goes to END after responding
    graph.add_edge("scout", END)
    graph.add_edge("master", END)
    graph.add_edge("troubleshooter", END)
    graph.add_edge("merchant", END)

    return graph.compile()


# Compiled graph ready to invoke
agent = build_graph()
