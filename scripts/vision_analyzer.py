"""
Vision Analyzer — Send page images to Claude Vision for structured data extraction.
Returns structured JSON with projects, materials, steps, blueprints, etc.
"""

import json
import logging
import os
import re
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from pdf_extractor import get_page_image_base64

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

VISION_MODEL = "claude-haiku-4-5-20251001"

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
- Return ONLY valid JSON, no other text
"""


def analyze_page(
    image_base64: str,
    page_number: int,
    raw_text_fallback: str = "",
    media_type: str = "image/png",
    max_tokens: int = 4096,
) -> dict:
    """
    Send a single page image to Claude Vision for structured extraction.

    Args:
        image_base64: Base64 encoded page image.
        page_number: 1-based page number (for logging).
        raw_text_fallback: OCR text to include as reference.
        media_type: MIME type of the image.
        max_tokens: Max response tokens.

    Returns:
        Parsed JSON dict from Claude, or a fallback dict on failure.
    """
    prompt_text = EXTRACTION_PROMPT
    if raw_text_fallback.strip():
        prompt_text += f"\n\nAlso, here is OCR-extracted text from this page for reference:\n{raw_text_fallback[:2000]}"

    user_content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_base64,
            },
        },
        {
            "type": "text",
            "text": prompt_text,
        },
    ]

    try:
        response = claude.messages.create(
            model=VISION_MODEL,
            max_tokens=max_tokens,
            system="You are a structured data extractor for craft books. Return ONLY valid JSON.",
            messages=[{"role": "user", "content": user_content}],
        )
        raw_response = response.content[0].text
        return _parse_json_robust(raw_response, page_number)

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


def _fix_json_string(text: str) -> str:
    """Fix common JSON issues from LLM output: trailing commas, unescaped chars."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Fix unescaped newlines inside string values (between quotes)
    # This is a best-effort fix for multi-line strings
    return text


def _parse_json_robust(raw_response: str, page_number: int) -> dict:
    """Try multiple strategies to parse JSON from Vision model output."""
    # Strategy 1: Direct parse
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract between first { and last }
    start = raw_response.find("{")
    end = raw_response.rfind("}")
    if start != -1 and end != -1 and end > start:
        extracted = raw_response[start : end + 1]

        # Strategy 2a: Direct parse of extracted
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

        # Strategy 2b: Fix trailing commas and retry
        fixed = _fix_json_string(extracted)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # Strategy 2c: Try removing the last problematic field before the error
        # Sometimes the model generates an incomplete field at the end due to token limit
        # Trim back to last complete entry
        for trim_char in ["},", "],", '"']:
            last_good = fixed.rfind(trim_char)
            if last_good > 0:
                candidate = fixed[: last_good + len(trim_char)]
                # Close any open structures
                open_braces = candidate.count("{") - candidate.count("}")
                open_brackets = candidate.count("[") - candidate.count("]")
                candidate += "]" * open_brackets + "}" * open_braces
                try:
                    result = json.loads(candidate)
                    logger.info(f"  Page {page_number}: Recovered JSON by trimming incomplete tail")
                    return result
                except json.JSONDecodeError:
                    continue

    # All strategies failed
    raise json.JSONDecodeError("All JSON parse strategies failed", raw_response, 0)


def analyze_all_pages(
    pages: list[dict],
    rate_limit_delay: float = 1.0,
    max_retries: int = 2,
    max_tokens: int = 4096,
) -> list[dict]:
    """
    Process all pages through Vision model with rate limiting and retries.

    Args:
        pages: Output from pdf_extractor.extract_pdf().
        rate_limit_delay: Seconds between API calls.
        max_retries: Retries on API failure per page.
        max_tokens: Max tokens per Vision response.

    Returns:
        List of dicts: [{"page_number": N, "extracted": {...}}, ...]
    """
    results = []
    total = len(pages)

    for page in pages:
        page_number = page["page_number"]
        image_path = page.get("image_path")

        # If no image was rendered, return raw text only
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

        # Load image as base64
        image_b64 = get_page_image_base64(Path(image_path))

        # Try with retries
        extracted = None
        for attempt in range(max_retries + 1):
            try:
                extracted = analyze_page(
                    image_base64=image_b64,
                    page_number=page_number,
                    raw_text_fallback=page.get("raw_text", ""),
                    max_tokens=max_tokens,
                )
                break
            except anthropic.RateLimitError:
                wait = (2 ** attempt) * 2
                logger.warning(f"[Vision] Page {page_number}: Rate limited, waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
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

        # Rate limit delay between calls
        if page_number < total:
            time.sleep(rate_limit_delay)

    return results
