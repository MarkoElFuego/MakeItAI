import os
import sys
import json
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import BaseModel
from supabase import create_client

# ── Setup ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from prompts.system_prompts import SYSTEM_PROMPT_RAG, ELFY_THINKING_MESSAGES

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# ── Clients ─────────────────────────────────────────────────────────────────
from google import genai
from google.genai import types

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_query",
    google_api_key=GOOGLE_API_KEY,
)

# ── FastAPI ─────────────────────────────────────────────────────────────────
app = FastAPI(title="MakeItAI — Elfy Premium", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    query_embedding = embeddings.embed_query(req.question)
    result = supabase.rpc(
        "match_documents",
        {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": 5,
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
    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant information found."

    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=f"Context:\n\n{context}\n\n---\n\nQuestion: {req.question}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT_RAG,
            temperature=0.4
        )
    )

    answer = getattr(response, "text", "")
    return AskResponse(answer=answer, sources=sources)


# ── LangGraph Agent ──────────────────────────────────────────────────────────
from agent.graph import agent as langgraph_agent, get_thinking_message


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []
    project_context: dict = {}
    tutorial_data: dict | None = None
    generated_image: str | None = None


class ChatResponse(BaseModel):
    response: str
    action: str
    thinking: str
    generated_image: str | None = None
    tutorial_data: dict | None = None
    sources: list[dict]
    conversation_history: list[dict]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main chat endpoint using LangGraph orchestrator."""
    result = langgraph_agent.invoke({
        "user_message": req.message,
        "action": "",
        "tutorial_data": req.tutorial_data,
        "generated_image": req.generated_image,
        "project_context": req.project_context,
        "conversation_history": req.conversation_history,
        "response": "",
        "sources": [],
        "thinking": "",
        "image_data": None,
    })

    return ChatResponse(
        response=result["response"],
        action=result.get("action", "chat_node"),
        thinking=result.get("thinking", ""),
        generated_image=result.get("generated_image"),
        tutorial_data=result.get("tutorial_data"),
        sources=result.get("sources", []),
        conversation_history=result.get("conversation_history", []),
    )


# ── SSE Streaming Chat ──────────────────────────────────────────────────────

def _sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events.
    
    Emits events:
      - thinking: {text: "⚒️ Elfy is forging..."}
      - token: {text: "word "}  
      - done: {response, action, thinking, tutorial_data, sources, conversation_history}
    """
    async def event_generator():
        # Phase 1: Send thinking message immediately
        # We need to determine the route first
        from agent.graph import route_message
        
        state = {
            "user_message": req.message,
            "action": "",
            "tutorial_data": req.tutorial_data,
            "generated_image": req.generated_image,
            "project_context": req.project_context,
            "conversation_history": req.conversation_history,
            "response": "",
            "sources": [],
            "thinking": "",
            "image_data": None,
        }
        
        # Route to determine which node
        node_name = route_message(state)
        thinking_msg = get_thinking_message(node_name)
        
        yield _sse_event("thinking", {"text": thinking_msg, "node": node_name})
        await asyncio.sleep(0.1)
        
        # Phase 2: Run the agent
        result = langgraph_agent.invoke(state)
        
        # Phase 3: Stream the response word by word
        response_text = result.get("response", "")
        words = response_text.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield _sse_event("token", {"text": token})
            await asyncio.sleep(0.03)  # 30ms between words for natural feel
        
        # Phase 4: Send final complete data
        yield _sse_event("done", {
            "response": response_text,
            "action": result.get("action", "chat_node"),
            "thinking": result.get("thinking", ""),
            "tutorial_data": result.get("tutorial_data"),
            "sources": result.get("sources", []),
            "conversation_history": result.get("conversation_history", []),
        })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ── Vision (Image Analysis) ─────────────────────────────────────────────────
from integrations.vision import analyze_image


class ImageRequest(BaseModel):
    image_base64: str
    media_type: str = "image/jpeg"
    message: str = "Please analyze this image."
    conversation_history: list[dict] = []


class ImageResponse(BaseModel):
    analysis: str
    phase: str


@app.post("/analyze-image", response_model=ImageResponse)
def analyze_image_endpoint(req: ImageRequest):
    """Analyze a craft image using Claude Vision."""
    analysis = analyze_image(
        image_base64=req.image_base64,
        media_type=req.media_type,
        user_message=req.message,
        conversation_history=req.conversation_history,
    )
    return ImageResponse(analysis=analysis, phase="HELPER")


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0", "name": "Elfy Premium"}
