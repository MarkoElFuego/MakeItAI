"""
MakeItAi – Vision Integration (Phase 3)

Analyzes user-uploaded images using Claude Vision API.
The craft mentor reviews work-in-progress photos and gives feedback.
"""

import base64
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from prompts.system_prompts import SYSTEM_PROMPT_VISION

claude = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

VISION_MODEL = "claude-haiku-4-5-20251001"


def analyze_image(
    image_base64: str,
    media_type: str = "image/jpeg",
    user_message: str = "Please analyze this image.",
    conversation_history: list[dict] | None = None,
) -> str:
    """
    Send an image to Claude Vision for craft analysis.

    Args:
        image_base64: Base64 encoded image data (no data:... prefix).
        media_type: MIME type (image/jpeg, image/png, image/webp, image/gif).
        user_message: Optional text accompanying the image.
        conversation_history: Previous messages for context.

    Returns:
        Analysis text from Claude.
    """
    history = conversation_history or []

    # Build the multimodal message
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
            "text": user_message,
        },
    ]

    messages = history + [{"role": "user", "content": user_content}]

    response = claude.messages.create(
        model=VISION_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT_VISION,
        messages=messages,
    )

    return response.content[0].text
