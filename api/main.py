import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import BaseModel
from supabase import create_client

# ── Setup ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from prompts.system_prompts import SYSTEM_PROMPT_RAG

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

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
app = FastAPI(title="MakeItAI", version="0.1.0")

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
    context = "\n\n---\n\n".join(context_parts) if context_parts else "Nema relevantnih informacija u bazi."
    
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=f"Kontekst iz knjiga:\n\n{context}\n\n---\n\nPitanje: {req.question}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT_RAG,
            temperature=0.4
        )
    )
    
    answer = getattr(response, "text", "")
    return AskResponse(answer=answer, sources=sources)


# ── LangGraph Agent ──────────────────────────────────────────────────────────
from agent.graph import agent as langgraph_agent


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []
    project_context: dict = {}
    tutorial_data: dict | None = None
    generated_image: str | None = None


class ChatResponse(BaseModel):
    response: str
    action: str
    status_text: str
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
    })
    
    # Map actions to display statuses
    status_map = {
        "chat_node": "Elfy is thinking...",
        "tutorial_gen_node": "Elfy is crafting your tutorial...",
        "help_node": "Elfy is thinking..."
    }
    
    return ChatResponse(
        response=result["response"],
        action=result.get("action", "chat_node"),
        status_text=status_map.get(result.get("action"), "Elfy is thinking..."),
        generated_image=result.get("generated_image"),
        tutorial_data=result.get("tutorial_data"),
        sources=result["sources"],
        conversation_history=result["conversation_history"],
    )


# ── Vision (Phase 3) ─────────────────────────────────────────────────────────
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

# ── FOLD Origami Integration ─────────────────────────────────────────────────
from integrations.fold_renderer import get_fold_index, get_fold_model, get_fold_svg
from fastapi.responses import PlainTextResponse


@app.get("/fold/models")
def list_fold_models():
    """List all available FOLD origami models."""
    return get_fold_index()


@app.get("/fold/{model_id}")
def get_fold(model_id: str):
    """Get a raw FOLD JSON object by model ID."""
    fold = get_fold_model(model_id)
    if not fold:
        return {"error": f"Model '{model_id}' not found"}
    return fold


@app.get("/fold/{model_id}/svg", response_class=PlainTextResponse)
def get_fold_svg_endpoint(model_id: str):
    """Render a FOLD model as SVG string."""
    svg = get_fold_svg(model_id)
    if not svg:
        return PlainTextResponse("Model not found", status_code=404)
    return PlainTextResponse(svg, media_type="image/svg+xml")


@app.get("/health")
def health():
    return {"status": "ok"}
