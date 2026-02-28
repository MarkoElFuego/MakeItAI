"""
Elfy – Image Generation via Gemini 3.1 Flash Image

Generates preview images of craft projects so users can SEE
what they'll be making before starting the tutorial.
"""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

IMAGE_MODEL = "gemini-3.1-flash-image-preview"


def generate_project_preview(
    project_description: str,
    materials: str = "",
    colors: str = "",
    style_hints: str = "",
) -> dict:
    """
    Generate a preview of a handmade craft project.

    Args:
        project_description: What the project is (e.g. "paper daffodil flowers").
        materials: Materials used (e.g. "yellow crepe paper, green wire").
        colors: Color palette (e.g. "yellow, orange, green").
        style_hints: Additional style info from RAG data.

    Returns:
        Dict with 'image_base64' (PNG), 'mime_type', 'success', 'error'.
    """
    parts = [
        f"Create a beautiful, clean, minimalist image of a handmade {project_description}.",
        "CRITICAL RULES: The image MUST ONLY SHOW THE CRAFT ITSELF. NO text, NO watermarks, NO hands, NO tools, NO extra decorative elements, NO background clutter.",
        "The craft should look handmade entirely out of paper and basic materials.",
        "Background: Clean, solid white or soft minimal background to isolate the design.",
        "Ensure the image is a perfect square (1:1 aspect ratio).",
    ]
    if materials:
        parts.append(f"Made from: {materials}.")
    if colors:
        parts.append(f"Color palette: {colors}.")
    if style_hints:
        parts.append(f"Additional details: {style_hints}.")

    prompt = " ".join(parts)

    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                raw = part.inline_data.data
                img_base64 = base64.b64encode(raw).decode("utf-8")
                mime = part.inline_data.mime_type or "image/png"
                return {
                    "image_base64": img_base64,
                    "mime_type": mime,
                    "success": True,
                    "error": None,
                }

        return {
            "image_base64": None,
            "mime_type": None,
            "success": False,
            "error": "No image in response",
        }

    except Exception as e:
        return {
            "image_base64": None,
            "mime_type": None,
            "success": False,
            "error": str(e),
        }
