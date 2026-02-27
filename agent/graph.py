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
    SYSTEM_PROMPT_CRAFTER,
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

Phase = Literal["SCOUT", "CRAFTER", "MASTER", "TROUBLESHOOTER", "MERCHANT"]


# ── State ────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    user_message: str
    current_phase: Phase
    project_context: dict          # material, tool, product, budget …
    conversation_history: list     # [{role, content}, …]
    response: str
    sources: list
    inspiration_images: list       # Pexels mood board images (SCOUT)
    craft_data: dict | None         # SVG step-by-step data (CRAFTER)


# ── Helper: RAG retrieval ────────────────────────────────────────────────────
def _rag_retrieve(
    question: str, top_k: int = 5, metadata_filter: dict | None = None
) -> tuple[str, list[dict]]:
    """Embed question, search Supabase, return (context_str, sources).

    Args:
        question: Text to embed and search for.
        top_k: Number of results to return.
        metadata_filter: Optional metadata filter (e.g. {"chunk_type": "blueprint"}).
            Uses match_documents_filtered RPC with jsonb @> operator.
    """
    query_embedding = embeddings.embed_query(question)

    if metadata_filter:
        result = supabase_client.rpc(
            "match_documents_filtered",
            {
                "query_embedding": query_embedding,
                "match_threshold": 0.3,
                "match_count": top_k,
                "filter": metadata_filter,
            },
        ).execute()
    else:
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


def _rag_retrieve_multi(
    question: str, chunk_types: list[str], top_k_per_type: int = 3
) -> tuple[str, list[dict]]:
    """Retrieve from multiple chunk_types and merge results."""
    all_parts = []
    all_sources = []
    seen_contents = set()
    for ct in chunk_types:
        context, sources = _rag_retrieve(
            question, top_k=top_k_per_type, metadata_filter={"chunk_type": ct}
        )
        for s in sources:
            key = s["content"][:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_sources.append(s)
        if context:
            all_parts.append(context)

    # Fallback: if filtered retrieval returned nothing, try unfiltered
    if not all_parts:
        return _rag_retrieve(question, top_k=top_k_per_type * len(chunk_types))

    return "\n\n---\n\n".join(all_parts), all_sources


# ── Helper: call Claude ──────────────────────────────────────────────────────
def _call_claude(system: str, messages: list[dict], model: str = NODE_MODEL) -> str:
    resp = claude.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    print(f"[Claude] Tokens — input: {resp.usage.input_tokens}, output: {resp.usage.output_tokens}")
    return resp.content[0].text


# ── Router ───────────────────────────────────────────────────────────────────
def route_message(state: AgentState) -> Phase:
    """Use Claude to classify the user message into a phase."""
    # Include conversation history so router has context for follow-up messages
    history = state.get("conversation_history", [])
    # Keep last 4 messages for context (to stay cheap on tokens)
    recent_history = history[-4:] if len(history) > 4 else history
    messages = recent_history + [{"role": "user", "content": state["user_message"]}]

    phase = _call_claude(
        system=SYSTEM_PROMPT_ROUTER,
        messages=messages,
        model=ROUTER_MODEL,
    ).strip().upper()

    valid = {"SCOUT", "CRAFTER", "MASTER", "TROUBLESHOOTER", "MERCHANT"}
    return phase if phase in valid else "CRAFTER"


# ── Helper: extract keywords for Pexels ──────────────────────────────────────
def _extract_keyword(user_message: str) -> str:
    """Use Claude to extract a short search keyword from the user message."""
    keyword = _call_claude(
        system=(
            "Extract 1-3 English keywords for an image search from the user's message. "
            "Return ONLY the keywords, nothing else. Example: 'paper flower bouquet'"
        ),
        messages=[{"role": "user", "content": user_message}],
        model=ROUTER_MODEL,
    ).strip().strip('"\'')
    return keyword


# ── Node: SCOUT (with Pexels mood board) ─────────────────────────────────────
def scout_node(state: AgentState) -> dict:
    from integrations.inspiration import search_inspiration

    history = state.get("conversation_history", [])
    messages = history + [{"role": "user", "content": state["user_message"]}]

    # Fetch inspiration images from Pexels
    keyword = _extract_keyword(state["user_message"])
    pexels_result = search_inspiration(keyword=keyword, per_page=6)
    images = pexels_result.get("images", [])

    # RAG: fetch project overviews for inspiration context
    rag_context, rag_sources = _rag_retrieve(
        state["user_message"], top_k=3, metadata_filter={"chunk_type": "overview"}
    )
    if rag_context:
        messages[-1] = {
            "role": "user",
            "content": (
                f"Related projects from craft books:\n\n{rag_context}\n\n---\n\n"
                f"{state['user_message']}"
            ),
        }

    answer = _call_claude(system=SYSTEM_PROMPT_SCOUT, messages=messages)

    return {
        "current_phase": "SCOUT",
        "response": answer,
        "sources": [],
        "inspiration_images": images,
        "conversation_history": messages + [{"role": "assistant", "content": answer}],
    }


# ── Node: CRAFTER (SVG step-by-step) ──────────────────────────────────────────
def crafter_node(state: AgentState) -> dict:
    import json as _json

    history = state.get("conversation_history", [])
    user_msg = state["user_message"]

    # If user message is vague ("this", "that", "it") and we have history,
    # extract what they actually want to make from conversation context
    rag_query = user_msg
    vague_words = {"this", "that", "it", "one", "make it", "show me", "let's do it"}
    is_vague = len(user_msg.split()) < 8 and any(w in user_msg.lower() for w in vague_words)

    if is_vague and history:
        # Ask Claude to extract the actual product from conversation
        extract_prompt = (
            "Based on the conversation below, what specific product does the user want to make? "
            "Reply with ONLY the product name (e.g. 'paper kusudama flower'). Nothing else."
        )
        extracted = _call_claude(
            system=extract_prompt,
            messages=history + [{"role": "user", "content": user_msg}],
            model=ROUTER_MODEL,
        ).strip()
        rag_query = extracted
        print(f"[CRAFTER] Extracted topic from context: '{extracted}'")

    # RAG — try blueprint+steps first, fallback to unfiltered
    context, sources = _rag_retrieve_multi(rag_query, ["blueprint", "steps"])
    high_quality_sources = [s for s in sources if s.get("similarity", 0) > 0.5]

    if high_quality_sources and context:
        user_content = (
            f"Reference from craft books:\n\n{context}\n\n---\n\n"
            f"User request: {user_msg}"
        )
    else:
        user_content = user_msg
        sources = []  # Don't return low-quality sources

    messages = history + [{"role": "user", "content": user_content}]

    # Use higher max_tokens for JSON+SVG output
    resp = claude.messages.create(
        model=NODE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT_CRAFTER,
        messages=messages,
    )
    raw = resp.content[0].text

    # Log token usage
    print(f"[CRAFTER] Tokens — input: {resp.usage.input_tokens}, output: {resp.usage.output_tokens}")

    # Parse JSON response — robust fallback
    craft_data = None
    try:
        craft_data = _json.loads(raw)
    except _json.JSONDecodeError:
        # Try extracting JSON block
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                craft_data = _json.loads(raw[start:end])
            except _json.JSONDecodeError:
                craft_data = None

    if craft_data and "steps" in craft_data:
        summary = f"Here's your build plan for **{craft_data.get('projectName', 'your project')}**! Follow the steps below."
    else:
        # JSON parsing failed — return raw text as normal response
        summary = raw
        craft_data = None

    clean_history = history + [
        {"role": "user", "content": state["user_message"]},
        {"role": "assistant", "content": summary},
    ]
    return {
        "current_phase": "CRAFTER",
        "response": summary,
        "sources": sources,
        "craft_data": craft_data,
        "conversation_history": clean_history,
    }


# ── Node: MASTER (uses RAG) ─────────────────────────────────────────────────
def master_node(state: AgentState) -> dict:
    context, sources = _rag_retrieve_multi(state["user_message"], ["steps", "tips"])

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
    graph.add_node("crafter", crafter_node)
    graph.add_node("master", master_node)
    graph.add_node("troubleshooter", troubleshooter_node)
    graph.add_node("merchant", merchant_node)

    # Entry: conditional routing based on user message
    graph.set_conditional_entry_point(
        route_message,
        {
            "SCOUT": "scout",
            "CRAFTER": "crafter",
            "MASTER": "master",
            "TROUBLESHOOTER": "troubleshooter",
            "MERCHANT": "merchant",
        },
    )

    # Each node goes to END after responding
    graph.add_edge("scout", END)
    graph.add_edge("crafter", END)
    graph.add_edge("master", END)
    graph.add_edge("troubleshooter", END)
    graph.add_edge("merchant", END)

    return graph.compile()


# Compiled graph ready to invoke
agent = build_graph()
