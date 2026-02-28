"""
MakeItAi – Vision Integration (Phase 3)

Analyzes user-uploaded images using Gemini Vision API.
The craft mentor reviews work-in-progress photos and gives feedback.
"""

import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from prompts.system_prompts import SYSTEM_PROMPT_VISION

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

VISION_MODEL = "gemini-3-flash-preview"


def analyze_image(
    image_base64: str,
    media_type: str = "image/jpeg",
    user_message: str = "Please analyze this image.",
    conversation_history: list[dict] | None = None,
) -> str:
    """
    Send an image to Gemini Vision for craft analysis.

    Args:
        image_base64: Base64 encoded image data (no data:... prefix).
        media_type: MIME type (image/jpeg, image/png, image/webp, image/gif).
        user_message: Optional text accompanying the image.
        conversation_history: Previous messages for context.

    Returns:
        Analysis text from Gemini.
    """
    history = conversation_history or []
    
    # Format the payload
    prompt_parts = []
    
    # Very basic history representation for one-shot
    for msg in history[-3:]:
        role = msg.get("role", "user")
        text = msg.get("content", "")
        if isinstance(text, str):
            prompt_parts.append(f"[{role}]: {text}")
            
    prompt_parts.append(
        types.Part.from_bytes(
            data=base64.b64decode(image_base64),
            mime_type=media_type,
        )
    )
    prompt_parts.append(user_message)

    response = client.models.generate_content(
        model=VISION_MODEL,
        contents=prompt_parts,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT_VISION,
            temperature=0.4,
        )
    )

    return getattr(response, "text", "")


# End of file
