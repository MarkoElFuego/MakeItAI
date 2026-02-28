import os
import sys
import json
import re
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from google import genai
from google.genai import types
from langgraph.graph import END, StateGraph
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from supabase import create_client
from typing_extensions import TypedDict

# ── Setup ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from prompts.system_prompts import (
    SYSTEM_PROMPT_ROUTER,
    SYSTEM_PROMPT_EXPLORER,
    SYSTEM_PROMPT_TUTORIAL_GEN,
    SYSTEM_PROMPT_VERIFIER,
    SYSTEM_PROMPT_HELPER,
)
# Vision import removed — image gen flow disabled

# ── Clients ──────────────────────────────────────────────────────────────────
gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

supabase_client = create_client(
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
)
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_query",
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

ROUTER_MODEL = "gemini-3-flash-preview"
NODE_MODEL = "gemini-3-flash-preview"
PLANNER_MODEL = "gemini-3-flash-preview"

NodeName = Literal["chat_node", "tutorial_gen_node", "help_node"]

# ── State ────────────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    user_message: str
    action: str
    tutorial_data: dict | None
    generated_image: str | None
    project_context: dict
    conversation_history: list
    response: str
    sources: list

# ── Helper: RAG retrieval ────────────────────────────────────────────────────
def _rag_retrieve(
    question: str, top_k: int = 5, metadata_filter: dict | None = None
) -> tuple[str, list[dict]]:
    query_embedding = embeddings.embed_query(question)
    if metadata_filter:
        result = supabase_client.rpc("match_documents_filtered", {"query_embedding": query_embedding, "match_threshold": 0.3, "match_count": top_k, "filter": metadata_filter}).execute()
    else:
        result = supabase_client.rpc("match_documents", {"query_embedding": query_embedding, "match_threshold": 0.3, "match_count": top_k}).execute()
    documents = result.data or []
    context_parts = []
    sources = []
    for doc in documents:
        context_parts.append(doc["content"])
        sources.append({"content": doc["content"][:200] + "...", "similarity": doc["similarity"], "metadata": doc.get("metadata", {})})
    context = "\n\n---\n\n".join(context_parts) if context_parts else ""
    return context, sources

def _rag_retrieve_multi(question: str, chunk_types: list[str], top_k_per_type: int = 3) -> tuple[str, list[dict]]:
    all_parts = []
    all_sources = []
    seen_contents = set()
    for ct in chunk_types:
        context, sources = _rag_retrieve(question, top_k=top_k_per_type, metadata_filter={"chunk_type": ct})
        for s in sources:
            key = s["content"][:100]
            if key not in seen_contents:
                seen_contents.add(key)
                all_sources.append(s)
        if context:
            all_parts.append(context)
    if not all_parts:
        return _rag_retrieve(question, top_k=top_k_per_type * len(chunk_types))
    return "\n\n---\n\n".join(all_parts), all_sources

# ── Helper: call LLM ──────────────────────────────────────────────────────
def _call_llm(
    system: str, messages: list[dict], model: str = NODE_MODEL, is_json: bool = False
) -> str:
    # Convert [{"role": ..., "content": ...}] to Gemini contents format
    # For a simple chat scenario without system attachments, we build string blocks or typed parts
    # Here we can just format it cleanly into simple prompts, or use types.Content.
    prompt_parts = []
    for msg in messages:
        role = msg.get("role", "user")
        text = msg.get("content", "")
        prompt_parts.append(f"[{role}]: {text}")
        
    config_args = {"system_instruction": system, "temperature": 0.2}
    if is_json:
        config_args["response_mime_type"] = "application/json"

    resp = gemini_client.models.generate_content(
        model=model,
        contents="\n\n".join(prompt_parts),
        config=types.GenerateContentConfig(**config_args)
    )
    
    return getattr(resp, "text", "")

def _verify_and_regenerate(system: str, messages: list[dict], model: str, initial_response: str, is_json: bool = False) -> str:
    verify_msg = f"Verify this response:\n{initial_response}"
    if is_json:
        verify_msg += "\nEnsure it is ONLY valid JSON, with no markdown code blocks."
    
    verify_resp = _call_llm(SYSTEM_PROMPT_VERIFIER, [{"role": "user", "content": verify_msg}], model=ROUTER_MODEL)
    if verify_resp.strip().upper().startswith("OK"):
        return initial_response
    else:
        print(f"[Verifier] Failed: {verify_resp}. Regenerating...")
        correction = f"Your previous response failed validation: {verify_resp}. Please correct it. Provide ONLY valid JSON." if is_json else f"Your previous response failed validation: {verify_resp}. Please correct it."
        new_messages = messages + [
            {"role": "assistant", "content": initial_response},
            {"role": "user", "content": correction}
        ]
        return _call_llm(system, new_messages, model=model, is_json=is_json)

# ── Router ───────────────────────────────────────────────────────────────────
def route_message(state: AgentState) -> NodeName:
    if state.get("tutorial_data") and any(w in state["user_message"].lower() for w in ["help", "explain", "ne ide"]):
        return "help_node"

    history = state.get("conversation_history", [])
    recent_history = history[-6:] if len(history) > 6 else history
    messages = recent_history + [{"role": "user", "content": state["user_message"]}]

    node = _call_llm(
        system=SYSTEM_PROMPT_ROUTER,
        messages=messages,
        model=ROUTER_MODEL,
    ).strip().lower()

    valid: set[NodeName] = {"chat_node", "tutorial_gen_node", "help_node"}
    result: NodeName = node if node in valid else "chat_node"
    print(f"[Router] '{state['user_message'][:50]}...' -> {result}")
    return result

# ── Nodes ────────────────────────────────────────────────────────────────────
def chat_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    messages = history + [{"role": "user", "content": state["user_message"]}]
    rag_context, rag_sources = _rag_retrieve(state["user_message"], top_k=3, metadata_filter={"chunk_type": "overview"})
    
    if rag_context:
        messages[-1] = {"role": "user", "content": f"Context:\n{rag_context}\n\nUser: {state['user_message']}"}
        
    answer = _call_llm(SYSTEM_PROMPT_EXPLORER, messages)
    answer = _verify_and_regenerate(SYSTEM_PROMPT_EXPLORER, messages, NODE_MODEL, answer)
    
    return {
        "action": "chat_node",
        "response": answer,
        "sources": rag_sources,
        "conversation_history": history + [
            {"role": "user", "content": state["user_message"]},
            {"role": "assistant", "content": answer}
        ]
    }

# Nodes logic

def tutorial_gen_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    ctx_messages = history[-6:] + [{"role": "user", "content": state["user_message"]}]
    project = _call_llm("Extract craft project name from history. Only name.", ctx_messages)
    context, sources = _rag_retrieve_multi(project, ["steps", "blueprint"])
    
    messages = history + [{"role": "user", "content": f"Context:\n{context}\n\nUser: {state['user_message']}"}]
    
    answer = _call_llm(SYSTEM_PROMPT_TUTORIAL_GEN, messages, model=PLANNER_MODEL, is_json=True)
    answer = _verify_and_regenerate(SYSTEM_PROMPT_TUTORIAL_GEN, messages, PLANNER_MODEL, answer, is_json=True)
    
    # Strip markdown if any
    clean_json = re.sub(r"```json\s*", "", answer).replace("```", "").strip()
    
    try:
        tut_data = json.loads(clean_json)
        
        # Extract fold_ops from steps and render SVGs using paper engine
        from integrations.paper_engine import build_tutorial_svgs
        fold_ops = []
        for step in tut_data.get("steps", []):
            fold_op = step.get("fold_op")
            if fold_op:
                fold_ops.append(fold_op)
        
        if fold_ops:
            svgs = build_tutorial_svgs(fold_ops)
            steps = tut_data.get("steps", [])
            svg_idx = 0
            for step in steps:
                if step.get("fold_op") and svg_idx < len(svgs):
                    step["svg"] = svgs[svg_idx]
                    svg_idx += 1
            print(f"[Paper Engine] Rendered {len(svgs)} step diagrams for '{project}'")
        else:
            print(f"[Paper Engine] No fold_ops found, tutorial has text only")
        
        print(f"[Tutorial JSON] {json.dumps(tut_data, indent=2, ensure_ascii=False)}")
        text_resp = "Here is your tutorial! Have fun!"
    except json.JSONDecodeError as e:
        print(f"JSON Parse Error: {e}\n{clean_json}")
        tut_data = None
        text_resp = "I had trouble generating the tutorial. Let's try again."

    return {
        "action": "tutorial_gen_node",
        "response": text_resp,
        "tutorial_data": tut_data,
        "sources": sources,
        "conversation_history": history + [
            {"role": "user", "content": state["user_message"]},
            {"role": "assistant", "content": text_resp}
        ]
    }

def help_node(state: AgentState) -> dict:
    history = state.get("conversation_history", [])
    user_msg = state["user_message"]
    
    # Extract step number from the user message (e.g. "step_index:3" injected by frontend)
    step_context = ""
    tut = state.get("tutorial_data")
    if tut and "step_index:" in user_msg:
        try:
            idx_str = user_msg.split("step_index:")[1].split("|")[0].strip()
            step_idx = int(idx_str)
            steps = tut.get("steps", [])
            if 0 <= step_idx < len(steps):
                s = steps[step_idx]
                step_context = (
                    f"--- CURRENT STEP CONTEXT ---\n"
                    f"Project: {tut.get('project_name', '')}\n"
                    f"Step {step_idx + 1} of {len(steps)}\n"
                    f"Title: {s.get('title', '')}\n"
                    f"Description: {s.get('description', '')}\n"
                    f"Materials: {', '.join(s.get('materials', []))}\n"
                    f"Tip: {s.get('tip', '')}\n"
                    f"---\n"
                )
        except (ValueError, IndexError):
            pass
    
    # Clean user message for display (remove the step_index metadata)
    clean_msg = user_msg.split("|")[-1].strip() if "|" in user_msg else user_msg
    
    prompt = f"{step_context}\nUser question: {clean_msg}" if step_context else clean_msg
    messages = history + [{"role": "user", "content": prompt}]
    
    answer = _call_llm(SYSTEM_PROMPT_HELPER, messages)
    
    return {
        "action": "help_node",
        "response": answer,
        "conversation_history": history + [
            {"role": "user", "content": clean_msg},
            {"role": "assistant", "content": answer}
        ]
    }

# ── Build graph ──────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("chat_node", chat_node)
    graph.add_node("tutorial_gen_node", tutorial_gen_node)
    graph.add_node("help_node", help_node)

    graph.set_conditional_entry_point(
        route_message,
        {
            "chat_node": "chat_node",
            "tutorial_gen_node": "tutorial_gen_node",
            "help_node": "help_node",
        },
    )

    for node in ["chat_node", "tutorial_gen_node", "help_node"]:
        graph.add_edge(node, END)

    return graph.compile()

# Compiled graph ready to invoke
agent = build_graph()
