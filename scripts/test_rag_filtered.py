"""
Quick test: verify filtered RAG retrieval works with new pipeline chunks.
Run: python scripts/test_rag_filtered.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from supabase import create_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

supabase_client = create_client(
    os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
)
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    task_type="retrieval_query",
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

PASS = 0
FAIL = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


def search(query, filter_meta=None, top_k=5):
    vec = embeddings.embed_query(query)
    if filter_meta:
        res = supabase_client.rpc(
            "match_documents_filtered",
            {
                "query_embedding": vec,
                "match_threshold": 0.3,
                "match_count": top_k,
                "filter": filter_meta,
            },
        ).execute()
    else:
        res = supabase_client.rpc(
            "match_documents",
            {
                "query_embedding": vec,
                "match_threshold": 0.3,
                "match_count": top_k,
            },
        ).execute()
    return res.data or []


# ── Test 1: Unfiltered search still works ────────────────────────────────────
print("\n1) Unfiltered search (backward compat)")
docs = search("ribbon heart card")
test("Returns results", len(docs) > 0, f"got {len(docs)}")
if docs:
    test("Has similarity score", "similarity" in docs[0])
    test("Has metadata", "metadata" in docs[0])

# ── Test 2: Filtered by chunk_type=blueprint ─────────────────────────────────
print("\n2) Filtered: chunk_type=blueprint")
docs = search("card dimensions", {"chunk_type": "blueprint"})
test("Returns results", len(docs) > 0, f"got {len(docs)}")
for d in docs:
    ct = (d.get("metadata") or {}).get("chunk_type", "?")
    test(f"  chunk_type is blueprint (got '{ct}')", ct == "blueprint")

# ── Test 3: Filtered by chunk_type=steps ─────────────────────────────────────
print("\n3) Filtered: chunk_type=steps")
docs = search("how to fold paper", {"chunk_type": "steps"})
test("Returns results", len(docs) > 0, f"got {len(docs)}")
for d in docs:
    ct = (d.get("metadata") or {}).get("chunk_type", "?")
    test(f"  chunk_type is steps (got '{ct}')", ct == "steps")

# ── Test 4: Filtered by chunk_type=overview ──────────────────────────────────
print("\n4) Filtered: chunk_type=overview")
docs = search("craft project ideas", {"chunk_type": "overview"})
test("Returns results", len(docs) > 0, f"got {len(docs)}")
for d in docs:
    ct = (d.get("metadata") or {}).get("chunk_type", "?")
    test(f"  chunk_type is overview (got '{ct}')", ct == "overview")

# ── Test 5: Filtered by chunk_type=materials ─────────────────────────────────
print("\n5) Filtered: chunk_type=materials")
docs = search("ribbon glue scissors", {"chunk_type": "materials"})
test("Returns results", len(docs) > 0, f"got {len(docs)}")
for d in docs:
    ct = (d.get("metadata") or {}).get("chunk_type", "?")
    test(f"  chunk_type is materials (got '{ct}')", ct == "materials")

# ── Test 6: Empty filter = unfiltered ────────────────────────────────────────
print("\n6) Empty filter (should behave like unfiltered)")
docs = search("ribbon heart card", {})
test("Returns results with empty filter", len(docs) > 0, f"got {len(docs)}")

# ── Test 7: Metadata has expected fields ─────────────────────────────────────
print("\n7) Metadata quality check")
docs = search("ribbon card", {"chunk_type": "overview"})
if docs:
    meta = docs[0].get("metadata", {})
    test("Has source_book", "source_book" in meta, str(meta.keys()))
    test("Has project_name", "project_name" in meta, str(meta.keys()))
    test("Has chunk_type", "chunk_type" in meta, str(meta.keys()))
    test("Has category", "category" in meta, str(meta.keys()))
    print(f"  Sample metadata: {meta}")
else:
    test("Got results for metadata check", False, "no results")

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL == 0:
    print("All tests passed! Filtered RAG retrieval works.")
else:
    print("Some tests failed — check output above.")
