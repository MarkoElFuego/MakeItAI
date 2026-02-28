"""
Vision Analyzer — Gemini Flash-Lite for structured data extraction from craft book pages.

Primary: gemini-2.5-flash-lite ($0.10/$0.40 per M tokens)
Fallback: gemini-2.5-flash (if dimensions missing on first pass)
Uses response_mime_type="application/json" for guaranteed valid JSON.
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from pdf_extractor import get_page_image_base64

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

PRIMARY_MODEL = "gemini-2.5-flash-lite"
FALLBACK_MODEL = "gemini-2.5-flash"

EXTRACTION_PROMPT = """You are analyzing a page from a craft instruction book.
Extract ALL information in this structured JSON format:

{
  "page_type": "project" | "tools_reference" | "materials_guide" | "introduction" | "table_of_contents" | "other",

  "projects": [
    {
      "name": "Project Name",
      "category": "paper_craft" | "leather" | "woodworking" | "textile" | "mixed_media" | "other",
      "difficulty": "beginner" | "intermediate" | "advanced",

      "materials": [
        {"item": "craftstock", "quantity": "1 piece", "dimensions": "5x5in", "color": "any"}
      ],

      "tools": [
        {"name": "bone folder", "purpose": "scoring folds", "optional": false}
      ],

      "steps": [
        {
          "step_number": 1,
          "instruction": "Score a crease down the center of the craftstock",
          "technique": "scoring",
          "dimensions_mentioned": ["5x5in", "center fold"],
          "visual_description": "Rectangle with dashed line down center"
        }
      ],

      "blueprint_data": {
        "pieces": [
          {
            "name": "card_base",
            "shape": "rectangle",
            "width": "5in",
            "height": "5in",
            "details": [
              {"type": "fold_line", "position": "vertical_center", "line_style": "dashed"}
            ]
          }
        ],
        "assembly_notes": "Fold card in half along score line"
      },

      "tips": ["Use screw punch for clean holes"],
      "finished_product_description": "A greeting card with a woven ribbon heart"
    }
  ],

  "tools_reference": [
    {"name": "Bone Folder", "use": "Score and burnish folds", "suitable_for": ["paper", "cardstock"]}
  ],

  "templates": [
    {
      "name": "Template Name",
      "scale": "enlarge 700%",
      "shape_description": "Rectangular strip with interlocking slits"
    }
  ],

  "diagram_descriptions": [
    "Photo showing finished ribbon card with heart pattern"
  ],

  "continuation_of_previous": false,
  "project_name_if_continuation": null
}

RULES:
    
- Extract EVERY dimension mentioned (inches, cm, mm)
- Describe EVERY visual/diagram you see in detail
- If you see a template/pattern, describe its EXACT shape and features
- Be precise about positions: "center", "top-left corner", "0.5in from edge"
- If a project continues from a previous page, set continuation_of_previous to true
- If the page has no craft content (copyright, blank, etc.), return: {"page_type": "other", "projects": []}

CRITICAL: Extract ALL content in ENGLISH regardless of 
    the source language (Russian, Chinese, Japanese, etc). 
    Translate all text, instructions, material names, and 
    technique descriptions to English. 
    Keep original measurements as-is (cm, mm, inches).

"""

SYSTEM_INSTRUCTION = "You are a structured data extractor for craft books. Return ONLY valid JSON matching the requested schema."


def _has_dimensions(extracted: dict) -> bool:
    """Check if extraction contains any dimension data in projects."""
    for proj in extracted.get("projects", []):
        for mat in proj.get("materials", []):
            if mat.get("dimensions"):
                return True
        for step in proj.get("steps", []):
            if step.get("dimensions_mentioned"):
                return True
        bp = proj.get("blueprint_data") or {}
        for piece in bp.get("pieces", []):
            if piece.get("width") or piece.get("height"):
                return True
    return False


def _call_gemini(
    model_name: str,
    image_base64: str,
    prompt_text: str,
    media_type: str = "image/png",
) -> dict:
    """Call Gemini Vision API with structured JSON output."""
    image_part = types.Part.from_bytes(
        data=__import__("base64").b64decode(image_base64),
        mime_type=media_type,
    )

    response = client.models.generate_content(
        model=model_name,
        contents=[image_part, prompt_text],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    raw = response.text
    return json.loads(raw)


def analyze_page(
    image_base64: str,
    page_number: int,
    raw_text_fallback: str = "",
    media_type: str = "image/png",
    **kwargs,
) -> dict:
    """
    Send a single page image to Gemini for structured extraction.

    Primary: gemini-2.5-flash-lite (cheap, fast)
    Fallback: gemini-2.5-flash (if no dimensions found on first pass)
    """
    prompt_text = EXTRACTION_PROMPT
    if raw_text_fallback.strip():
        prompt_text += f"\n\nAlso, here is OCR-extracted text from this page for reference:\n{raw_text_fallback[:2000]}"

    try:
        # Primary: Flash-Lite
        extracted = _call_gemini(PRIMARY_MODEL, image_base64, prompt_text, media_type)

        # Check if dimensions were missed — retry with stronger model
        if extracted.get("page_type") == "project" and not _has_dimensions(extracted):
            logger.info(f"  Page {page_number}: No dimensions found, retrying with {FALLBACK_MODEL}")
            try:
                fallback = _call_gemini(FALLBACK_MODEL, image_base64, prompt_text, media_type)
                if _has_dimensions(fallback):
                    logger.info(f"  Page {page_number}: Fallback found dimensions")
                    return fallback
            except Exception as e:
                logger.warning(f"  Page {page_number}: Fallback failed: {e}")

        return extracted

    except json.JSONDecodeError as e:
        logger.warning(f"  Page {page_number}: JSON parse failed: {e}")
        return {
            "page_type": "error",
            "projects": [],
            "error": f"JSON parse error: {e}",
            "raw_text": raw_text_fallback[:500],
        }
    except Exception as e:
        logger.error(f"  Page {page_number}: Vision API error: {e}")
        return {
            "page_type": "error",
            "projects": [],
            "error": str(e),
            "raw_text": raw_text_fallback[:500],
        }


def analyze_all_pages(
    pages: list[dict],
    rate_limit_delay: float = 1.0,
    max_retries: int = 2,
    **kwargs,
) -> list[dict]:
    """
    Process all pages through Gemini Vision with rate limiting and retries.
    """
    results = []
    total = len(pages)

    for page in pages:
        page_number = page["page_number"]
        image_path = page.get("image_path")

        if not image_path or not Path(image_path).exists():
            logger.warning(f"[Vision] Page {page_number}/{total}: No image, using raw text only")
            results.append({
                "page_number": page_number,
                "extracted": {
                    "page_type": "text_only",
                    "projects": [],
                    "raw_text": page.get("raw_text", ""),
                },
            })
            continue

        image_b64 = get_page_image_base64(Path(image_path))

        extracted = None
        for attempt in range(max_retries + 1):
            try:
                extracted = analyze_page(
                    image_base64=image_b64,
                    page_number=page_number,
                    raw_text_fallback=page.get("raw_text", ""),
                )
                break
            except Exception as e:
                if attempt < max_retries:
                    wait = (2 ** attempt) * 2
                    logger.warning(f"[Vision] Page {page_number}: Error {e}, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    logger.error(f"[Vision] Page {page_number}: Failed after {max_retries + 1} attempts: {e}")
                    extracted = {
                        "page_type": "error",
                        "projects": [],
                        "error": str(e),
                    }

        if extracted is None:
            extracted = {"page_type": "error", "projects": [], "error": "All retries exhausted"}

        results.append({"page_number": page_number, "extracted": extracted})

        projects_found = len(extracted.get("projects", []))
        page_type = extracted.get("page_type", "unknown")
        logger.info(f"[Vision] Page {page_number}/{total}: type={page_type}, projects={projects_found}")

        if page_number < total:
            time.sleep(rate_limit_delay)

    return results
