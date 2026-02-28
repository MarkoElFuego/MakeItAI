"""
FOLD File Integration — Serve origami .fold files and render as SVG
"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FOLD_DIR = PROJECT_ROOT / "data" / "fold"


def get_fold_index() -> list[dict]:
    """Return the list of available FOLD models."""
    index_path = FOLD_DIR / "index.json"
    if not index_path.exists():
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("models", [])


def get_fold_model(model_id: str) -> dict | None:
    """Load a .fold file by model ID from index."""
    index = get_fold_index()
    entry = next((m for m in index if m["id"] == model_id), None)
    if not entry:
        return None
    fold_path = FOLD_DIR / entry["file"]
    if not fold_path.exists():
        return None
    with open(fold_path, "r", encoding="utf-8") as f:
        fold_data = json.load(f)
    fold_data["_meta"] = entry
    return fold_data


def _compute_transform(fold_data, width=340, height=260):
    """Compute coordinate transform from FOLD coords to SVG pixel space."""
    vertices = fold_data.get("vertices_coords", [])
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = max_x - min_x if max_x != min_x else 1
    range_y = max_y - min_y if max_y != min_y else 1
    pad = 30
    draw_w = width - 2 * pad
    draw_h = height - 2 * pad - 30
    scale = min(draw_w / range_x, draw_h / range_y)

    def tx(x): return pad + (x - min_x) * scale + (draw_w - range_x * scale) / 2
    def ty(y): return pad + (y - min_y) * scale + (draw_h - range_y * scale) / 2
    return tx, ty


STYLE_MAP = {
    "B": {"stroke": "#8B7355", "width": "2", "dasharray": ""},
    "M": {"stroke": "#E74C3C", "width": "1.5", "dasharray": "6,4"},
    "V": {"stroke": "#3B82F6", "width": "1.5", "dasharray": "6,4"},
    "F": {"stroke": "#CCC", "width": "1", "dasharray": "3,3"},
    "U": {"stroke": "#CCC", "width": "1", "dasharray": ""},
    "C": {"stroke": "#8B7355", "width": "2.5", "dasharray": "2,2"},
}


def fold_to_svg(fold_data: dict, width: int = 340, height: int = 260, lang: str = "sr") -> str:
    """Convert a FOLD object to SVG using Elfy's design system colors."""
    vertices = fold_data.get("vertices_coords", [])
    edges = fold_data.get("edges_vertices", [])
    assignments = fold_data.get("edges_assignment", [])
    if not vertices or not edges:
        return ""

    # Localized labels
    labels = {
        "sr": {"M": "planinski nabor", "V": "dolinski nabor", "B": "ivica"},
        "en": {"M": "mountain fold", "V": "valley fold", "B": "edge"},
    }
    lang_labels = labels.get(lang, labels["en"])

    tx, ty = _compute_transform(fold_data, width, height)

    lines = []
    lines.append(f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'  <rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#FFF9F0"/>')

    # Paper shadow + fill
    pxs = [tx(v[0]) for v in vertices]
    pys = [ty(v[1]) for v in vertices]
    px1, px2, py1, py2 = min(pxs), max(pxs), min(pys), max(pys)
    lines.append(f'  <rect x="{px1+3:.1f}" y="{py1+3:.1f}" width="{px2-px1:.1f}" height="{py2-py1:.1f}" rx="2" fill="#E8D5C0" opacity="0.4"/>')
    lines.append(f'  <rect x="{px1:.1f}" y="{py1:.1f}" width="{px2-px1:.1f}" height="{py2-py1:.1f}" rx="2" fill="#FFFEF5" stroke="#8B7355" stroke-width="1"/>')

    for order_type in ["B", "F", "U", "C", "V", "M"]:
        for i, edge in enumerate(edges):
            a = assignments[i] if i < len(assignments) else "U"
            if a != order_type:
                continue
            v0, v1 = vertices[edge[0]], vertices[edge[1]]
            s = STYLE_MAP.get(a, STYLE_MAP["U"])
            dash = f' stroke-dasharray="{s["dasharray"]}"' if s["dasharray"] else ""
            lines.append(
                f'  <line x1="{tx(v0[0]):.1f}" y1="{ty(v0[1]):.1f}" '
                f'x2="{tx(v1[0]):.1f}" y2="{ty(v1[1]):.1f}" '
                f'stroke="{s["stroke"]}" stroke-width="{s["width"]}"{dash}/>'
            )

    # Legend
    ly = height - 20
    used = set(assignments)
    lx = 20
    for a_type, color, _ in [("M", "#E74C3C", ""), ("V", "#3B82F6", ""), ("B", "#8B7355", "")]:
        if a_type in used:
            label = lang_labels.get(a_type, a_type)
            dash = ' stroke-dasharray="6,4"' if a_type in ("M", "V") else ""
            lines.append(f'  <line x1="{lx}" y1="{ly}" x2="{lx+20}" y2="{ly}" stroke="{color}" stroke-width="1.5"{dash}/>')
            lines.append(f'  <text x="{lx+25}" y="{ly+4}" font-size="9" fill="#666">{label}</text>')
            lx += 110

    lines.append('</svg>')
    return "\n".join(lines)


def get_fold_svg(model_id: str) -> str | None:
    fold = get_fold_model(model_id)
    if not fold:
        return None
    return fold_to_svg(fold)


# ── FOLD model matching ──────────────────────────────────────────────────────

def match_fold_model(project_name: str) -> dict | None:
    """Try to match a project name to a FOLD model by name/tags."""
    index = get_fold_index()
    name_lower = project_name.lower().strip()

    for entry in index:
        candidates = [
            entry["id"],
            entry.get("name_en", "").lower(),
            entry.get("name_sr", "").lower(),
        ] + [t.lower() for t in entry.get("tags", [])]

        for c in candidates:
            if c and (c in name_lower or name_lower in c):
                return get_fold_model(entry["id"])
    return None


def fold_to_svg_step(
    fold_data: dict,
    highlight_edges: list[int] | None = None,
    step_label: str = "",
    width: int = 340,
    height: int = 260,
) -> str:
    """
    Render FOLD SVG with specific edges highlighted and others ghosted.
    If highlight_edges is None, render all edges normally.
    """
    vertices = fold_data.get("vertices_coords", [])
    edges = fold_data.get("edges_vertices", [])
    assignments = fold_data.get("edges_assignment", [])
    if not vertices or not edges:
        return ""

    tx, ty = _compute_transform(fold_data, width, height)
    highlight_set = set(highlight_edges) if highlight_edges is not None else None
    ghost = {"stroke": "#DDD", "width": "0.8", "dasharray": "3,3"}

    lines = []
    lines.append(f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'  <rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#FFF9F0"/>')

    pxs, pys = [tx(v[0]) for v in vertices], [ty(v[1]) for v in vertices]
    px1, px2, py1, py2 = min(pxs), max(pxs), min(pys), max(pys)
    lines.append(f'  <rect x="{px1+3:.1f}" y="{py1+3:.1f}" width="{px2-px1:.1f}" height="{py2-py1:.1f}" rx="2" fill="#E8D5C0" opacity="0.4"/>')
    lines.append(f'  <rect x="{px1:.1f}" y="{py1:.1f}" width="{px2-px1:.1f}" height="{py2-py1:.1f}" rx="2" fill="#FFFEF5" stroke="#8B7355" stroke-width="1"/>')

    for i, edge in enumerate(edges):
        a = assignments[i] if i < len(assignments) else "U"
        v0, v1 = vertices[edge[0]], vertices[edge[1]]
        x1, y1, x2, y2 = tx(v0[0]), ty(v0[1]), tx(v1[0]), ty(v1[1])

        if highlight_set is not None and i not in highlight_set:
            if a == "B":
                lines.append(f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#8B7355" stroke-width="2"/>')
            else:
                lines.append(f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{ghost["stroke"]}" stroke-width="{ghost["width"]}" stroke-dasharray="{ghost["dasharray"]}"/>')
        else:
            s = STYLE_MAP.get(a, STYLE_MAP["U"])
            w = "2.5" if highlight_set is not None else s["width"]
            dash = f' stroke-dasharray="{s["dasharray"]}"' if s["dasharray"] else ""
            lines.append(f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{s["stroke"]}" stroke-width="{w}"{dash}/>')

    if step_label:
        lines.append(f'  <text x="{width//2}" y="18" text-anchor="middle" font-size="11" fill="#8B7355" font-weight="600">{step_label}</text>')

    ly = height - 20
    lines.append(f'  <line x1="20" y1="{ly}" x2="40" y2="{ly}" stroke="#E74C3C" stroke-width="1.5" stroke-dasharray="6,4"/>')
    lines.append(f'  <text x="45" y="{ly+4}" font-size="9" fill="#666">mountain</text>')
    lines.append(f'  <line x1="110" y1="{ly}" x2="130" y2="{ly}" stroke="#3B82F6" stroke-width="1.5" stroke-dasharray="6,4"/>')
    lines.append(f'  <text x="135" y="{ly+4}" font-size="9" fill="#666">valley</text>')
    lines.append(f'  <line x1="190" y1="{ly}" x2="210" y2="{ly}" stroke="#DDD" stroke-width="1" stroke-dasharray="3,3"/>')
    lines.append(f'  <text x="215" y="{ly+4}" font-size="9" fill="#666">prethodni</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def generate_fold_step_svgs(fold_data: dict, num_steps: int = 8) -> list[str]:
    """
    Generate progressive SVGs from a FOLD model, revealing edges step-by-step.
    Step 0: Full crease pattern overview.
    Steps 1..N: Progressive reveal of fold groups.
    """
    assignments = fold_data.get("edges_assignment", [])
    crease_edges = [i for i, a in enumerate(assignments) if a in ("M", "V")]
    svgs = [fold_to_svg_step(fold_data, highlight_edges=None, step_label="Crease Pattern")]

    if not crease_edges:
        return svgs

    actual = min(num_steps - 1, len(crease_edges))
    chunk = max(1, len(crease_edges) // actual) if actual > 0 else 1

    for step in range(actual):
        start = step * chunk
        end = start + chunk if step < actual - 1 else len(crease_edges)
        svgs.append(fold_to_svg_step(fold_data, highlight_edges=crease_edges[start:end], step_label=f"Fold {step + 1}"))

    return svgs
