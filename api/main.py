import os
import sys
from pathlib import Path

import anthropic
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
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
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
    # 1. Embed the question
    query_embedding = embeddings.embed_query(req.question)

    # 2. Similarity search in Supabase (top 5)
    result = supabase.rpc(
        "match_documents",
        {
            "query_embedding": query_embedding,
            "match_threshold": 0.3,
            "match_count": 5,
        },
    ).execute()

    documents = result.data or []

    # 3. Build context from retrieved chunks
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

    # 4. Send to Claude Haiku
    message = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=SYSTEM_PROMPT_RAG,
        messages=[
            {
                "role": "user",
                "content": f"Kontekst iz knjiga:\n\n{context}\n\n---\n\nPitanje: {req.question}",
            }
        ],
    )

    answer = message.content[0].text

    return AskResponse(answer=answer, sources=sources)


# ── LangGraph Agent ──────────────────────────────────────────────────────────
from agent.graph import agent as langgraph_agent


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []
    project_context: dict = {}


class ChatResponse(BaseModel):
    response: str
    phase: str
    sources: list[dict]
    conversation_history: list[dict]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Main chat endpoint using LangGraph orchestrator."""
    result = langgraph_agent.invoke({
        "user_message": req.message,
        "current_phase": "MASTER",
        "project_context": req.project_context,
        "conversation_history": req.conversation_history,
        "response": "",
        "sources": [],
    })
    return ChatResponse(
        response=result["response"],
        phase=result["current_phase"],
        sources=result["sources"],
        conversation_history=result["conversation_history"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}
