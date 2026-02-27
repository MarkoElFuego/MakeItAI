"""
Project Grouper — Merge multi-page projects from Vision extraction results.
A project spanning pages 5-7 gets combined into a single project record.
"""

import logging
import re

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Lowercase, strip whitespace and punctuation for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _merge_lists_unique(list_a: list, list_b: list) -> list:
    """Merge two lists, preserving order, removing exact duplicates."""
    seen = set()
    result = []
    for item in list_a + list_b:
        key = str(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _merge_blueprint_data(bp_a: dict | None, bp_b: dict | None) -> dict:
    """Merge two blueprint_data dicts."""
    if not bp_a:
        return bp_b or {}
    if not bp_b:
        return bp_a

    merged = {
        "pieces": _merge_lists_unique(
            bp_a.get("pieces", []), bp_b.get("pieces", [])
        ),
        "assembly_notes": "\n".join(
            filter(None, [bp_a.get("assembly_notes", ""), bp_b.get("assembly_notes", "")])
        ),
    }
    return merged


def group_by_project(page_extractions: list[dict], source_book: str) -> list[dict]:
    """
    Group Vision extraction results by project, merging multi-page projects.

    Args:
        page_extractions: Output from vision_analyzer.analyze_all_pages().
            Each item: {"page_number": N, "extracted": {...}}
        source_book: PDF filename for metadata.

    Returns:
        List of merged project dicts with all data consolidated.
    """
    # Ordered dict of projects by normalized name
    projects = {}  # normalized_name -> project dict
    name_map = {}  # normalized_name -> original name

    # Collect non-project data (tools reference, templates)
    all_tools_reference = []
    all_templates = []
    all_diagram_descriptions = []

    for page_data in sorted(page_extractions, key=lambda x: x["page_number"]):
        page_num = page_data["page_number"]
        extracted = page_data.get("extracted", {})

        if extracted.get("page_type") in ("error", "text_only"):
            continue

        # Collect book-level reference data
        all_tools_reference = _merge_lists_unique(
            all_tools_reference, extracted.get("tools_reference", [])
        )
        all_templates = _merge_lists_unique(
            all_templates, extracted.get("templates", [])
        )
        all_diagram_descriptions = _merge_lists_unique(
            all_diagram_descriptions, extracted.get("diagram_descriptions", [])
        )

        # Check if this page is a continuation of a previous project
        is_continuation = extracted.get("continuation_of_previous", False)
        continuation_name = extracted.get("project_name_if_continuation")

        for project in extracted.get("projects", []):
            proj_name = project.get("name", "Unknown Project")

            # Determine if this should merge with an existing project
            if is_continuation and continuation_name:
                norm_key = _normalize_name(continuation_name)
            else:
                norm_key = _normalize_name(proj_name)

            if norm_key in projects:
                # Merge into existing project
                existing = projects[norm_key]
                existing["page_numbers"].append(page_num)
                existing["materials"] = _merge_lists_unique(
                    existing["materials"], project.get("materials", [])
                )
                existing["tools"] = _merge_lists_unique(
                    existing["tools"], project.get("tools", [])
                )

                # Append steps (re-number later)
                new_steps = project.get("steps", [])
                existing["steps"].extend(new_steps)

                existing["blueprint_data"] = _merge_blueprint_data(
                    existing.get("blueprint_data"), project.get("blueprint_data")
                )
                existing["tips"] = _merge_lists_unique(
                    existing["tips"], project.get("tips", [])
                )

                # Merge diagram descriptions
                existing["diagram_descriptions"] = _merge_lists_unique(
                    existing.get("diagram_descriptions", []),
                    extracted.get("diagram_descriptions", []),
                )

                if project.get("finished_product_description"):
                    existing["finished_product_description"] = project[
                        "finished_product_description"
                    ]

            else:
                # New project entry
                name_map[norm_key] = proj_name
                projects[norm_key] = {
                    "project_name": proj_name,
                    "category": project.get("category", "other"),
                    "difficulty": project.get("difficulty", "beginner"),
                    "page_numbers": [page_num],
                    "source_book": source_book,
                    "materials": project.get("materials", []),
                    "tools": project.get("tools", []),
                    "steps": project.get("steps", []),
                    "blueprint_data": project.get("blueprint_data") or {},
                    "tips": project.get("tips", []),
                    "diagram_descriptions": extracted.get("diagram_descriptions", []),
                    "templates": extracted.get("templates", []),
                    "finished_product_description": project.get(
                        "finished_product_description", ""
                    ),
                }

    # Re-number steps sequentially for each project
    result = []
    for norm_key, proj in projects.items():
        for i, step in enumerate(proj["steps"]):
            step["step_number"] = i + 1
        proj["page_numbers"] = sorted(set(proj["page_numbers"]))
        result.append(proj)

    # Add reference data as a special pseudo-project if any exists
    if all_tools_reference or all_templates:
        result.append({
            "project_name": "_book_reference",
            "category": "reference",
            "difficulty": "n/a",
            "page_numbers": [],
            "source_book": source_book,
            "materials": [],
            "tools": [],
            "steps": [],
            "blueprint_data": {},
            "tips": [],
            "diagram_descriptions": all_diagram_descriptions,
            "templates": all_templates,
            "tools_reference": all_tools_reference,
            "finished_product_description": "",
        })

    logger.info(
        f"Grouped {sum(len(e.get('extracted', {}).get('projects', [])) for e in page_extractions)} "
        f"page-level projects into {len(result)} merged projects"
    )

    return result
