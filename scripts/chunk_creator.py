"""
Chunk Creator — Create semantic chunks with rich metadata from grouped projects.
Produces 5 chunk types: overview, materials, steps, blueprint, tips.
"""

import logging

logger = logging.getLogger(__name__)


def _format_material(mat) -> str:
    """Format a material dict or string into readable text."""
    if isinstance(mat, str):
        return mat
    parts = [mat.get("item", "unknown")]
    if mat.get("quantity"):
        parts.append(f"({mat['quantity']})")
    if mat.get("dimensions"):
        parts.append(f"- {mat['dimensions']}")
    if mat.get("color"):
        parts.append(f"[{mat['color']}]")
    return " ".join(parts)


def _format_tool(tool) -> str:
    """Format a tool dict or string into readable text."""
    if isinstance(tool, str):
        return tool
    parts = [tool.get("name", "unknown")]
    if tool.get("purpose"):
        parts.append(f"— {tool['purpose']}")
    if tool.get("optional"):
        parts.append("(optional)")
    return " ".join(parts)


def _format_step(step) -> str:
    """Format a step dict into readable text."""
    if isinstance(step, str):
        return step
    num = step.get("step_number", "?")
    instruction = step.get("instruction", "")
    text = f"Step {num}: {instruction}"
    if step.get("technique"):
        text += f" [Technique: {step['technique']}]"
    if step.get("dimensions_mentioned"):
        dims = ", ".join(step["dimensions_mentioned"])
        text += f" [Dimensions: {dims}]"
    if step.get("visual_description"):
        text += f" (Visual: {step['visual_description']})"
    return text


def _base_metadata(project: dict, source_book: str, chunk_type: str) -> dict:
    """Create base metadata dict shared by all chunks for a project."""
    return {
        "source_book": source_book,
        "project_name": project["project_name"],
        "category": project.get("category", "other"),
        "difficulty": project.get("difficulty", "beginner"),
        "chunk_type": chunk_type,
        "page_numbers": project.get("page_numbers", []),
    }


def create_chunks_for_project(project: dict, source_book: str) -> list[dict]:
    """
    Create semantic chunks from a single grouped project.

    Chunk types:
      overview  — project summary (name, category, difficulty, materials count, steps count)
      materials — full materials and tools list
      steps     — groups of 3 steps per chunk
      blueprint — blueprint data with dimensions, shapes, pieces
      tips      — tips and finishing description

    Args:
        project: One item from project_grouper.group_by_project().
        source_book: PDF filename.

    Returns:
        List of chunk dicts: [{"content": str, "metadata": dict}, ...]
    """
    chunks = []
    name = project["project_name"]

    # Skip the _book_reference pseudo-project for now (handled separately)
    if name == "_book_reference":
        return _create_reference_chunks(project, source_book)

    materials = project.get("materials") or []
    tools = project.get("tools") or []
    steps = project.get("steps") or []
    blueprint = project.get("blueprint_data") or {}
    tips = project.get("tips") or []

    # 1. OVERVIEW chunk
    mat_names = [_format_material(m).split(" (")[0] for m in materials[:5]]
    tool_names = [_format_tool(t).split(" —")[0] for t in tools[:5]]
    overview_text = (
        f"Project: {name}. "
        f"Category: {project.get('category', 'craft')}. "
        f"Difficulty: {project.get('difficulty', 'beginner')}. "
        f"Materials needed: {', '.join(mat_names) if mat_names else 'see details'}. "
        f"Tools: {', '.join(tool_names) if tool_names else 'basic craft tools'}. "
        f"This project has {len(steps)} steps."
    )
    if project.get("finished_product_description"):
        overview_text += f" Result: {project['finished_product_description']}"

    chunks.append({
        "content": overview_text,
        "metadata": _base_metadata(project, source_book, "overview"),
    })

    # 2. MATERIALS chunk (if any materials or tools)
    if materials or tools:
        mat_lines = [f"- {_format_material(m)}" for m in materials]
        tool_lines = [f"- {_format_tool(t)}" for t in tools]
        materials_text = f"Materials and tools for {name}:\n\n"
        if mat_lines:
            materials_text += "Materials:\n" + "\n".join(mat_lines) + "\n\n"
        if tool_lines:
            materials_text += "Tools:\n" + "\n".join(tool_lines)

        chunks.append({
            "content": materials_text.strip(),
            "metadata": {
                **_base_metadata(project, source_book, "materials"),
                "has_dimensions": any(
                    isinstance(m, dict) and m.get("dimensions") for m in materials
                ),
            },
        })

    # 3. STEPS chunks (groups of 3)
    steps_per_chunk = 3
    for i in range(0, len(steps), steps_per_chunk):
        step_group = steps[i : i + steps_per_chunk]
        first = step_group[0].get("step_number", i + 1) if isinstance(step_group[0], dict) else i + 1
        last = step_group[-1].get("step_number", i + len(step_group)) if isinstance(step_group[-1], dict) else i + len(step_group)
        step_range = f"{first}-{last}" if first != last else str(first)

        step_lines = [_format_step(s) for s in step_group]
        steps_text = f"Steps for {name} (steps {step_range}):\n\n" + "\n\n".join(step_lines)

        # Collect dimensions and techniques from this group
        dimensions = []
        techniques = []
        tools_used = []
        for s in step_group:
            if isinstance(s, dict):
                dimensions.extend(s.get("dimensions_mentioned") or [])
                if s.get("technique"):
                    techniques.append(s["technique"])

        chunks.append({
            "content": steps_text,
            "metadata": {
                **_base_metadata(project, source_book, "steps"),
                "step_range": step_range,
                "has_dimensions": bool(dimensions),
                "dimensions": dimensions,
                "techniques": techniques,
            },
        })

    # 4. BLUEPRINT chunk (only if blueprint data exists and is non-empty)
    pieces = blueprint.get("pieces") or []
    assembly = blueprint.get("assembly_notes") or ""
    if pieces or assembly:
        bp_lines = []
        for piece in pieces:
            if isinstance(piece, dict):
                piece_desc = f"Piece: {piece.get('name', 'unnamed')}"
                if piece.get("shape"):
                    piece_desc += f", shape: {piece['shape']}"
                if piece.get("width"):
                    piece_desc += f", width: {piece['width']}"
                if piece.get("height"):
                    piece_desc += f", height: {piece['height']}"
                details = piece.get("details") or []
                for d in details:
                    if isinstance(d, dict):
                        piece_desc += f"\n  - {d.get('type', '')}: {d.get('position', '')} ({d.get('line_style', '')})"
                bp_lines.append(piece_desc)
            else:
                bp_lines.append(str(piece))

        blueprint_text = f"Blueprint/template data for {name}:\n\n"
        if bp_lines:
            blueprint_text += "Pieces:\n" + "\n".join(bp_lines) + "\n\n"
        if assembly:
            blueprint_text += f"Assembly: {assembly}\n\n"

        # Add diagram descriptions if any
        diagrams = project.get("diagram_descriptions", [])
        if diagrams:
            blueprint_text += "Diagrams: " + "; ".join(str(d) for d in diagrams)

        # Collect all measurements
        all_measurements = []
        for piece in pieces:
            if isinstance(piece, dict):
                for key in ("width", "height"):
                    if piece.get(key):
                        all_measurements.append(piece[key])

        chunks.append({
            "content": blueprint_text.strip(),
            "metadata": {
                **_base_metadata(project, source_book, "blueprint"),
                "has_dimensions": bool(all_measurements),
                "dimensions": all_measurements,
            },
        })

    # 5. TIPS chunk (only if tips exist)
    if tips:
        tip_lines = [f"- {t}" if isinstance(t, str) else f"- {t}" for t in tips]
        tips_text = f"Tips and notes for {name}:\n\n" + "\n".join(tip_lines)
        if project.get("finished_product_description"):
            tips_text += f"\n\nFinished product: {project['finished_product_description']}"

        chunks.append({
            "content": tips_text,
            "metadata": _base_metadata(project, source_book, "tips"),
        })

    return chunks


def _create_reference_chunks(project: dict, source_book: str) -> list[dict]:
    """Create chunks for the _book_reference pseudo-project (tools, templates)."""
    chunks = []

    tools_ref = project.get("tools_reference", [])
    if tools_ref:
        lines = []
        for tool in tools_ref:
            if isinstance(tool, dict):
                line = f"- {tool.get('name', 'unknown')}: {tool.get('use', '')}"
                if tool.get("suitable_for"):
                    line += f" (for: {', '.join(tool['suitable_for'])})"
                lines.append(line)
            else:
                lines.append(f"- {tool}")

        chunks.append({
            "content": f"Tools reference from {source_book}:\n\n" + "\n".join(lines),
            "metadata": {
                "source_book": source_book,
                "project_name": "_book_reference",
                "category": "reference",
                "difficulty": "n/a",
                "chunk_type": "tools_reference",
                "page_numbers": project.get("page_numbers", []),
            },
        })

    templates = project.get("templates", [])
    if templates:
        lines = []
        for tmpl in templates:
            if isinstance(tmpl, dict):
                line = f"- {tmpl.get('name', 'unnamed')}"
                if tmpl.get("scale"):
                    line += f" (scale: {tmpl['scale']})"
                if tmpl.get("shape_description"):
                    line += f": {tmpl['shape_description']}"
                lines.append(line)
            else:
                lines.append(f"- {tmpl}")

        chunks.append({
            "content": f"Templates from {source_book}:\n\n" + "\n".join(lines),
            "metadata": {
                "source_book": source_book,
                "project_name": "_book_reference",
                "category": "reference",
                "difficulty": "n/a",
                "chunk_type": "templates",
                "page_numbers": project.get("page_numbers", []),
            },
        })

    return chunks


def create_all_chunks(grouped_projects: list[dict], source_book: str) -> list[dict]:
    """
    Create chunks for all projects.

    Args:
        grouped_projects: Output from project_grouper.group_by_project().
        source_book: PDF filename.

    Returns:
        Flat list of all chunk dicts.
    """
    all_chunks = []
    for project in grouped_projects:
        chunks = create_chunks_for_project(project, source_book)
        all_chunks.extend(chunks)
        logger.info(
            f"  Project '{project['project_name']}': {len(chunks)} chunks created"
        )

    logger.info(f"Total: {len(all_chunks)} chunks from {len(grouped_projects)} projects")
    return all_chunks
