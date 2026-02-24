import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from supabase import create_client

# ── Setup ───────────────────────────────────────────────────────────────────
load_dotenv()

GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

PROCESSED_FILE = (
    Path(__file__).resolve().parent.parent
    / "knowledge"
    / "processed"
    / "cleaned_book.json"
)
BATCH_SIZE = 20


def main():
    # ── Connect to Supabase ─────────────────────────────────────────────
    print("Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # ── Initialize embeddings model ─────────────────────────────────────
    print("Initializing Google Generative AI Embeddings...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        task_type="retrieval_document",
        google_api_key=GOOGLE_API_KEY,
    )

    # ── Load cleaned book data ──────────────────────────────────────────
    print(f"Loading processed data from {PROCESSED_FILE}...")
    with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cleaned_text = data["cleaned_text"]
    source = data.get("source", PROCESSED_FILE.name)

    # ── Remove residual LLM artifacts ───────────────────────────────────
    cleaned_text = re.sub(
        r"(?i)here is the corrected text[:\s]*", "", cleaned_text
    )

    # ── Split into chunks ───────────────────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    chunks = splitter.split_text(cleaned_text)
    total = len(chunks)
    print(f"Split text into {total} chunks.")

    # ── Generate embeddings and prepare rows ────────────────────────────
    rows = []
    for i, chunk in enumerate(chunks):
        print(f"Generating embedding for chunk {i + 1}/{total}...")
        embedding = embeddings.embed_query(chunk)
        rows.append(
            {
                "content": chunk,
                "metadata": {"source": source, "chunk_index": i},
                "embedding": embedding,
            }
        )

    # ── Insert into Supabase in batches ─────────────────────────────────
    print(f"Inserting {total} rows into Supabase table 'documents'...")
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        supabase.table("documents").insert(batch).execute()
        end = min(start + BATCH_SIZE, total)
        print(f"  Inserted batch {start + 1}–{end} of {total}")
        time.sleep(0.5)

    print("Ingestion complete!")


if __name__ == "__main__":
    main()
