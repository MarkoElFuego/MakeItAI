"""
RAG Ingestion Pipeline — Main orchestrator.

Processes PDF craft books through:
  1. PDF extraction (pages → images + text)
  2. Vision analysis (structured JSON per page)
  3. Project grouping (merge multi-page projects)
  4. Semantic chunking (overview, materials, steps, blueprint, tips)
  5. Embedding + upload to Supabase

Usage:
  python scripts/ingest_pipeline.py                    # Process all from inbox/
  python scripts/ingest_pipeline.py --file book.pdf    # Process one file
  python scripts/ingest_pipeline.py --reprocess        # Re-upload (ignore duplicates)
  python scripts/ingest_pipeline.py --dry-run          # Preview without uploading
"""

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from supabase import create_client

# Ensure scripts/ is on the path so we can import sibling modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdf_extractor import extract_pdf
from vision_analyzer import analyze_all_pages
from project_grouper import group_by_project
from chunk_creator import create_all_chunks

# ── Setup ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(config_path: Path | None = None) -> dict:
    """Load pipeline_config.yaml or return defaults."""
    default_path = PROJECT_ROOT / "config" / "pipeline_config.yaml"
    path = config_path or default_path

    defaults = {
        "vision": {"model": "claude-haiku-4-5-20251001", "max_tokens": 2048, "rate_limit_delay": 1.0, "max_retries": 2},
        "embedding": {"model": "models/gemini-embedding-001", "task_type": "retrieval_document", "batch_size": 20, "batch_delay": 0.5},
        "chunking": {"max_chunk_size": 1000, "steps_per_chunk": 3},
        "paths": {"inbox": "knowledge/inbox", "processing": "knowledge/processing", "done": "knowledge/done", "extracted": "knowledge/extracted"},
        "page_dpi": 200,
        "cleanup_images": False,
    }

    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        # Merge loaded into defaults
        for key in defaults:
            if key in loaded:
                if isinstance(defaults[key], dict) and isinstance(loaded[key], dict):
                    defaults[key].update(loaded[key])
                else:
                    defaults[key] = loaded[key]
        return defaults
    else:
        logger.warning(f"Config not found at {path}, using defaults")
        return defaults


def ensure_directories(config: dict):
    """Create pipeline directories if they don't exist."""
    for key in ("inbox", "processing", "done", "extracted"):
        path = PROJECT_ROOT / config["paths"][key]
        path.mkdir(parents=True, exist_ok=True)


def check_existing_chunks(supabase_client, source_book: str, project_name: str, chunk_type: str) -> bool:
    """
    Check if chunks for this source+project+type already exist in Supabase.
    Returns True if exists (skip), False if new (insert).
    """
    try:
        result = (
            supabase_client.table("documents")
            .select("id", count="exact")
            .filter("metadata->>source_book", "eq", source_book)
            .filter("metadata->>project_name", "eq", project_name)
            .filter("metadata->>chunk_type", "eq", chunk_type)
            .execute()
        )
        return (result.count or 0) > 0
    except Exception as e:
        logger.warning(f"Idempotency check failed: {e}")
        return False


def embed_and_upload(
    chunks: list[dict],
    embeddings_model: GoogleGenerativeAIEmbeddings,
    supabase_client,
    batch_size: int = 20,
    batch_delay: float = 0.5,
    dry_run: bool = False,
    reprocess: bool = False,
) -> int:
    """
    Embed chunks with Gemini and upload to Supabase.

    Returns:
        Number of chunks actually inserted.
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would embed and upload {len(chunks)} chunks")
        for c in chunks:
            meta = c["metadata"]
            logger.info(f"  - {meta.get('project_name', '?')} / {meta.get('chunk_type', '?')}")
        return 0

    # Group by source+project+type for idempotency check
    to_insert = []
    skipped = 0

    for chunk in chunks:
        meta = chunk["metadata"]
        if not reprocess and check_existing_chunks(
            supabase_client,
            meta.get("source_book", ""),
            meta.get("project_name", ""),
            meta.get("chunk_type", ""),
        ):
            skipped += 1
            continue
        to_insert.append(chunk)

    if skipped:
        logger.info(f"Skipped {skipped} existing chunks (use --reprocess to override)")

    if not to_insert:
        logger.info("No new chunks to upload")
        return 0

    # Generate embeddings and prepare rows
    rows = []
    total = len(to_insert)
    for i, chunk in enumerate(to_insert):
        logger.info(f"Embedding chunk {i + 1}/{total}...")
        try:
            embedding = embeddings_model.embed_query(chunk["content"])
            rows.append({
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "embedding": embedding,
            })
        except Exception as e:
            logger.error(f"Embedding failed for chunk {i + 1}: {e}")
            continue

    # Insert into Supabase in batches
    inserted = 0
    logger.info(f"Inserting {len(rows)} rows into Supabase...")
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        try:
            supabase_client.table("documents").insert(batch).execute()
            end = min(start + batch_size, len(rows))
            inserted += len(batch)
            logger.info(f"  Inserted batch {start + 1}-{end} of {len(rows)}")
        except Exception as e:
            logger.error(f"  Batch insert failed at {start}: {e}")
        time.sleep(batch_delay)

    return inserted


def process_single_pdf(
    pdf_path: Path,
    config: dict,
    embeddings_model: GoogleGenerativeAIEmbeddings,
    supabase_client,
    dry_run: bool = False,
    reprocess: bool = False,
) -> dict:
    """
    Run the full pipeline for one PDF.

    Returns:
        {"pdf": str, "pages": int, "projects": int, "chunks_created": int,
         "chunks_inserted": int, "errors": list}
    """
    pdf_name = pdf_path.stem
    source_book = pdf_path.name
    errors = []

    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {source_book}")
    logger.info(f"{'='*60}")

    # Step 1: Extract pages
    processing_dir = PROJECT_ROOT / config["paths"]["processing"] / pdf_name
    logger.info(f"\n[Step 1/5] Extracting pages...")
    pages = extract_pdf(pdf_path, processing_dir, dpi=config.get("page_dpi", 200))

    if not pages:
        errors.append("No pages extracted from PDF")
        return {"pdf": source_book, "pages": 0, "projects": 0, "chunks_created": 0, "chunks_inserted": 0, "errors": errors}

    logger.info(f"  Extracted {len(pages)} pages")

    # Step 2: Vision analysis
    vision_cfg = config.get("vision", {})
    logger.info(f"\n[Step 2/5] Vision analysis ({len(pages)} pages)...")
    page_extractions = analyze_all_pages(
        pages,
        rate_limit_delay=vision_cfg.get("rate_limit_delay", 1.0),
        max_retries=vision_cfg.get("max_retries", 2),
        max_tokens=vision_cfg.get("max_tokens", 2048),
    )

    # Save raw extraction for debugging
    extracted_dir = PROJECT_ROOT / config["paths"]["extracted"] / pdf_name
    extracted_dir.mkdir(parents=True, exist_ok=True)
    extraction_file = extracted_dir / "extraction.json"
    try:
        with open(extraction_file, "w", encoding="utf-8") as f:
            json.dump(page_extractions, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"  Saved extraction data to {extraction_file}")
    except Exception as e:
        logger.warning(f"  Failed to save extraction: {e}")

    # Count errors in extraction
    extraction_errors = [p for p in page_extractions if p.get("extracted", {}).get("page_type") == "error"]
    if extraction_errors:
        errors.append(f"{len(extraction_errors)} pages had Vision errors")

    # Step 3: Group by project
    logger.info(f"\n[Step 3/5] Grouping by project...")
    grouped_projects = group_by_project(page_extractions, source_book)
    logger.info(f"  Found {len(grouped_projects)} projects")

    for proj in grouped_projects:
        logger.info(f"    - {proj['project_name']} (pages: {proj['page_numbers']}, "
                     f"steps: {len(proj.get('steps', []))}, category: {proj.get('category', '?')})")

    # Step 4: Create chunks
    logger.info(f"\n[Step 4/5] Creating semantic chunks...")
    chunks = create_all_chunks(grouped_projects, source_book)
    logger.info(f"  Created {len(chunks)} chunks total")

    # Step 5: Embed and upload
    embed_cfg = config.get("embedding", {})
    logger.info(f"\n[Step 5/5] Embedding and uploading to Supabase...")
    inserted = embed_and_upload(
        chunks,
        embeddings_model,
        supabase_client,
        batch_size=embed_cfg.get("batch_size", 20),
        batch_delay=embed_cfg.get("batch_delay", 0.5),
        dry_run=dry_run,
        reprocess=reprocess,
    )

    # Cleanup: move PDF to done/
    if not dry_run:
        done_dir = PROJECT_ROOT / config["paths"]["done"]
        done_dir.mkdir(parents=True, exist_ok=True)
        done_path = done_dir / source_book
        try:
            shutil.move(str(pdf_path), str(done_path))
            logger.info(f"\n  Moved PDF to {done_path}")
        except Exception as e:
            logger.warning(f"  Could not move PDF: {e}")

    # Optionally clean up page images
    if config.get("cleanup_images", False) and processing_dir.exists():
        shutil.rmtree(processing_dir, ignore_errors=True)
        logger.info(f"  Cleaned up page images in {processing_dir}")

    return {
        "pdf": source_book,
        "pages": len(pages),
        "projects": len(grouped_projects),
        "chunks_created": len(chunks),
        "chunks_inserted": inserted,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="RAG Ingestion Pipeline for craft books")
    parser.add_argument("--file", type=str, help="Process a specific PDF file")
    parser.add_argument("--reprocess", action="store_true", help="Re-upload all chunks (ignore duplicates)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without uploading to Supabase")
    parser.add_argument("--config", type=str, help="Path to config YAML file")
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)
    ensure_directories(config)

    # Initialize clients
    logger.info("Initializing clients...")
    embed_cfg = config.get("embedding", {})
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model=embed_cfg.get("model", "models/gemini-embedding-001"),
        task_type=embed_cfg.get("task_type", "retrieval_document"),
        google_api_key=os.environ["GOOGLE_API_KEY"],
    )
    supabase_client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )

    # Determine which PDFs to process
    if args.file:
        pdf_path = Path(args.file)
        if not pdf_path.is_absolute():
            pdf_path = PROJECT_ROOT / pdf_path
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            sys.exit(1)
        pdf_files = [pdf_path]
    else:
        inbox = PROJECT_ROOT / config["paths"]["inbox"]
        pdf_files = sorted(inbox.glob("*.pdf"))
        if not pdf_files:
            logger.info(f"No PDF files found in {inbox}")
            logger.info("Place PDF files in knowledge/inbox/ and run again.")
            sys.exit(0)

    logger.info(f"Found {len(pdf_files)} PDF(s) to process")
    if args.dry_run:
        logger.info("[DRY RUN MODE — no data will be written to Supabase]")

    # Process each PDF
    start_time = time.time()
    results = []
    for pdf_path in pdf_files:
        result = process_single_pdf(
            pdf_path, config, embeddings_model, supabase_client,
            dry_run=args.dry_run, reprocess=args.reprocess,
        )
        results.append(result)

    # Print summary
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"PIPELINE COMPLETE — {elapsed:.1f}s")
    logger.info(f"{'='*60}")

    total_pages = sum(r["pages"] for r in results)
    total_projects = sum(r["projects"] for r in results)
    total_chunks = sum(r["chunks_created"] for r in results)
    total_inserted = sum(r["chunks_inserted"] for r in results)
    total_errors = sum(len(r["errors"]) for r in results)

    for r in results:
        status = "OK" if not r["errors"] else f"WARNINGS: {', '.join(r['errors'])}"
        logger.info(f"  {r['pdf']}: {r['pages']} pages, {r['projects']} projects, "
                     f"{r['chunks_created']} chunks ({r['chunks_inserted']} uploaded) — {status}")

    logger.info(f"\nTotals: {len(results)} PDFs, {total_pages} pages, {total_projects} projects, "
                 f"{total_chunks} chunks, {total_inserted} uploaded, {total_errors} warnings")

    # Save run log
    log_file = PROJECT_ROOT / "knowledge" / "pipeline_log.json"
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "dry_run": args.dry_run,
        "reprocess": args.reprocess,
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }
    try:
        existing_log = []
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8") as f:
                existing_log = json.load(f)
        existing_log.append(log_entry)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(existing_log, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not save run log: {e}")


if __name__ == "__main__":
    main()
