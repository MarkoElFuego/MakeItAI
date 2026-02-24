import json
import re
from pathlib import Path

import ollama

RAW_FILE = Path(__file__).resolve().parent.parent / "knowledge" / "raw" / "392184411-The-Paper-Craft-Book.txt"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "knowledge" / "processed" / "cleaned_book.json"
CHUNK_SIZE = 2000  # characters per chunk sent to the LLM
MODEL = "llama3"


def read_raw_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def remove_page_markers(text: str) -> str:
    """Remove lines that look like <page X>."""
    return re.sub(r"(?m)^<page\s+\d+>\s*$\n?", "", text)


def chunk_text(text: str, size: int) -> list[str]:
    """Split text into chunks of roughly `size` characters, breaking at newlines."""
    chunks = []
    while text:
        if len(text) <= size:
            chunks.append(text)
            break
        # Find the last newline within the size limit
        split_at = text.rfind("\n", 0, size)
        if split_at == -1:
            split_at = size
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def clean_chunk_with_llm(chunk: str) -> str:
    """Send a chunk to Ollama and ask it to fix OCR errors and broken lines."""
    prompt = (
        "You are a helpful text-cleaning assistant. "
        "The following text was extracted via OCR and contains errors such as "
        "broken lines, garbled characters, and misspellings. "
        "Please fix the text so it reads naturally. "
        "Only return the corrected text, nothing else.\n\n"
        f"---\n{chunk}\n---"
    )

    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


def main():
    print(f"Reading raw file: {RAW_FILE}")
    raw_text = read_raw_text(RAW_FILE)

    print("Removing <page X> markers...")
    text = remove_page_markers(raw_text)

    chunks = chunk_text(text, CHUNK_SIZE)
    print(f"Split text into {len(chunks)} chunks of ~{CHUNK_SIZE} chars each.")

    cleaned_chunks = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"Processing chunk {i}/{len(chunks)} with {MODEL}...")
        cleaned = clean_chunk_with_llm(chunk)
        cleaned_chunks.append(cleaned)

    cleaned_text = "\n\n".join(cleaned_chunks)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "source": RAW_FILE.name,
        "model": MODEL,
        "total_chunks": len(chunks),
        "cleaned_text": cleaned_text,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Cleaned text saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
