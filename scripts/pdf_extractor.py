"""
PDF Extractor — Extract pages as images (PNG) and raw text from PDF files.
Uses PyMuPDF (fitz) for both text extraction and page rendering.
"""

import base64
import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_pdf(pdf_path: Path, output_dir: Path, dpi: int = 200) -> list[dict]:
    """
    Extract all pages from a PDF as images and raw text.

    Args:
        pdf_path: Path to the source PDF file.
        output_dir: Directory to write page images into.
        dpi: Resolution for page rendering (default 200).

    Returns:
        List of dicts, one per page:
        [{"page_number": 1, "image_path": Path, "raw_text": str}, ...]
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pages = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.error(f"Failed to open PDF {pdf_path}: {e}")
        return pages

    total = len(doc)
    logger.info(f"Extracting {total} pages from {pdf_path.name}")

    for i, page in enumerate(doc):
        page_number = i + 1
        page_data = {
            "page_number": page_number,
            "image_path": None,
            "raw_text": "",
        }

        # Extract raw text
        try:
            page_data["raw_text"] = page.get_text("text")
        except Exception as e:
            logger.warning(f"  Page {page_number}/{total}: text extraction failed: {e}")

        # Render page as PNG
        try:
            pix = page.get_pixmap(dpi=dpi)
            image_path = output_dir / f"page_{page_number:03d}.png"
            pix.save(str(image_path))
            page_data["image_path"] = image_path
        except Exception as e:
            logger.warning(f"  Page {page_number}/{total}: image render failed: {e}")

        pages.append(page_data)
        logger.info(f"  Page {page_number}/{total} extracted"
                     f" (text: {len(page_data['raw_text'])} chars,"
                     f" image: {'OK' if page_data['image_path'] else 'FAILED'})")

    doc.close()
    return pages


def get_page_image_base64(image_path: Path) -> str:
    """Read a page image file and return its base64 encoding."""
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")
