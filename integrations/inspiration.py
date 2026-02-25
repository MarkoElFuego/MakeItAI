"""
MakeItAi – Inspiration / Mood Board Integration (Phase 3)

Uses Pexels API (free) to find inspiration images for craft projects.
Returns curated image results that can serve as a mood board.
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


def search_inspiration(
    keyword: str,
    per_page: int = 10,
    orientation: str = "landscape",
) -> dict:
    """
    Search Pexels for inspiration images.

    Args:
        keyword: Search term (e.g. "paper flower", "wooden cutting board").
        per_page: Number of results (max 80, default 10).
        orientation: "landscape", "portrait", or "square".

    Returns:
        Dict with 'images' list and 'total_results' count.
    """
    if not PEXELS_API_KEY:
        return {
            "error": "PEXELS_API_KEY not set in .env",
            "images": [],
            "total_results": 0,
        }

    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": keyword,
        "per_page": min(per_page, 80),
        "orientation": orientation,
    }

    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params)

    if resp.status_code != 200:
        return {
            "error": f"Pexels API error: {resp.status_code}",
            "images": [],
            "total_results": 0,
        }

    data = resp.json()
    images = []
    for photo in data.get("photos", []):
        images.append({
            "id": photo["id"],
            "description": photo.get("alt", ""),
            "photographer": photo["photographer"],
            "url_original": photo["src"]["original"],
            "url_large": photo["src"]["large"],
            "url_medium": photo["src"]["medium"],
            "url_small": photo["src"]["small"],
            "url_page": photo["url"],
        })

    return {
        "keyword": keyword,
        "images": images,
        "total_results": data.get("total_results", 0),
    }
