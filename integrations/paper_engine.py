"""
Paper Folding Engine — Deterministic SVG renderer for paper craft tutorials.

Instead of asking the LLM to draw SVGs (which produces bad results),
the LLM outputs structured fold operations, and this engine renders
accurate 2D diagrams showing before→after transformations.

Supported operations:
  - valley_fold: Fold paper toward you along a line
  - mountain_fold: Fold paper away from you along a line
  - cut: Cut paper along a line (remove one side)
  - rotate: Rotate the paper
  - flip: Flip the paper over
"""
import math
from typing import Optional


# ── Geometry helpers ────────────────────────────────────────────────────────

def _reflect_point(px: float, py: float, lx1: float, ly1: float, lx2: float, ly2: float) -> tuple[float, float]:
    """Reflect point (px, py) across line defined by (lx1,ly1)-(lx2,ly2)."""
    dx = lx2 - lx1
    dy = ly2 - ly1
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return (px, py)
    t = ((px - lx1) * dx + (py - ly1) * dy) / len_sq
    proj_x = lx1 + t * dx
    proj_y = ly1 + t * dy
    return (2 * proj_x - px, 2 * proj_y - py)


def _side_of_line(px: float, py: float, lx1: float, ly1: float, lx2: float, ly2: float) -> float:
    """Returns positive if point is on left side, negative if right, 0 if on line."""
    return (lx2 - lx1) * (py - ly1) - (ly2 - ly1) * (px - lx1)


def _line_segment_intersection(
    ax1: float, ay1: float, ax2: float, ay2: float,
    bx1: float, by1: float, bx2: float, by2: float,
) -> Optional[tuple[float, float]]:
    """Find intersection of two line segments, or None."""
    dax = ax2 - ax1
    day = ay2 - ay1
    dbx = bx2 - bx1
    dby = by2 - by1
    denom = dax * dby - day * dbx
    if abs(denom) < 1e-10:
        return None
    t = ((bx1 - ax1) * dby - (by1 - ay1) * dbx) / denom
    s = ((bx1 - ax1) * day - (by1 - ay1) * dax) / denom
    if -1e-10 <= t <= 1 + 1e-10 and -1e-10 <= s <= 1 + 1e-10:
        return (ax1 + t * dax, ay1 + t * day)
    return None


def _split_polygon(
    polygon: list[tuple[float, float]],
    lx1: float, ly1: float, lx2: float, ly2: float,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Split polygon by line into left-side and right-side polygons."""
    left = []
    right = []
    n = len(polygon)
    for i in range(n):
        curr = polygon[i]
        nxt = polygon[(i + 1) % n]
        side_curr = _side_of_line(curr[0], curr[1], lx1, ly1, lx2, ly2)
        side_next = _side_of_line(nxt[0], nxt[1], lx1, ly1, lx2, ly2)

        if side_curr >= 0:
            left.append(curr)
        if side_curr <= 0:
            right.append(curr)

        # If edge crosses the line, add intersection point to both
        if (side_curr > 1e-10 and side_next < -1e-10) or (side_curr < -1e-10 and side_next > 1e-10):
            pt = _line_segment_intersection(
                curr[0], curr[1], nxt[0], nxt[1],
                lx1, ly1, lx2, ly2
            )
            if pt:
                left.append(pt)
                right.append(pt)

    return left, right


# ── Paper State ─────────────────────────────────────────────────────────────

class PaperState:
    """Represents the current state of a piece of paper as a 2D polygon."""

    def __init__(self, size: float = 1.0):
        """Start with a square of given size."""
        self.layers: list[list[tuple[float, float]]] = [
            [(0, 0), (size, 0), (size, size), (0, size)]
        ]
        self.size = size

    @property
    def outline(self) -> list[tuple[float, float]]:
        """Return the top layer outline."""
        return self.layers[0] if self.layers else []

    def valley_fold(self, line_from: tuple[float, float], line_to: tuple[float, float], fold_side: str = "bottom"):
        """
        Valley fold: fold one side of the paper over the fold line.
        fold_side: which side to fold ("bottom", "top", "left", "right")
        — determines which part moves.
        """
        lx1, ly1 = line_from
        lx2, ly2 = line_to
        new_layers = []

        for polygon in self.layers:
            left, right = _split_polygon(polygon, lx1, ly1, lx2, ly2)

            if fold_side in ("bottom", "right"):
                # Fold the right/bottom side over
                if right:
                    reflected = [_reflect_point(p[0], p[1], lx1, ly1, lx2, ly2) for p in right]
                    new_layers.append(reflected)
                if left:
                    new_layers.append(left)
            else:
                # Fold the left/top side over
                if left:
                    reflected = [_reflect_point(p[0], p[1], lx1, ly1, lx2, ly2) for p in left]
                    new_layers.append(reflected)
                if right:
                    new_layers.append(right)

        self.layers = new_layers if new_layers else self.layers

    def mountain_fold(self, line_from: tuple[float, float], line_to: tuple[float, float], fold_side: str = "bottom"):
        """Mountain fold — same geometry, different visual indication."""
        self.valley_fold(line_from, line_to, fold_side)

    def cut(self, line_from: tuple[float, float], line_to: tuple[float, float], keep_side: str = "left"):
        """Cut paper along a line, keeping one side."""
        lx1, ly1 = line_from
        lx2, ly2 = line_to
        new_layers = []
        for polygon in self.layers:
            left, right = _split_polygon(polygon, lx1, ly1, lx2, ly2)
            if keep_side == "left" and left:
                new_layers.append(left)
            elif keep_side == "right" and right:
                new_layers.append(right)
        self.layers = new_layers if new_layers else self.layers

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Get bounding box (min_x, min_y, max_x, max_y) of all layers."""
        all_pts = [p for layer in self.layers for p in layer]
        if not all_pts:
            return (0, 0, self.size, self.size)
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def clone(self) -> "PaperState":
        """Deep copy the paper state."""
        new = PaperState.__new__(PaperState)
        new.layers = [list(layer) for layer in self.layers]
        new.size = self.size
        return new


# ── SVG Renderer ────────────────────────────────────────────────────────────

def _polygon_to_svg_path(polygon: list[tuple[float, float]], tx, ty) -> str:
    """Convert polygon vertices to SVG path d attribute."""
    if not polygon:
        return ""
    parts = [f"M {tx(polygon[0][0]):.1f} {ty(polygon[0][1]):.1f}"]
    for p in polygon[1:]:
        parts.append(f"L {tx(p[0]):.1f} {ty(p[1]):.1f}")
    parts.append("Z")
    return " ".join(parts)


def render_step_svg(
    before: PaperState,
    after: PaperState,
    fold_line: Optional[tuple[tuple[float, float], tuple[float, float]]] = None,
    fold_type: str = "valley_fold",
    action_label: str = "",
    width: int = 340,
    height: int = 260,
) -> str:
    """
    Render a before→after SVG showing the paper transformation.
    Left side: before state with fold line marked
    Center: transformation arrow
    Right side: after state
    """
    # Layout: A on left (x: 20-155), arrow (x: 155-185), B on right (x: 185-320)
    a_center_x, a_center_y = 87, 115
    b_center_x, b_center_y = 253, 115
    half_w = 65  # max half-width for each shape

    def _make_transform(state: PaperState, cx: float, cy: float):
        """Create transform functions to fit state into a box centered at (cx, cy)."""
        bx1, by1, bx2, by2 = state.get_bounds()
        sw = bx2 - bx1 if bx2 != bx1 else 1
        sh = by2 - by1 if by2 != by1 else 1
        scale = min(half_w * 2 / sw, (height - 80) / sh)
        ox = cx - (bx1 + sw / 2) * scale
        oy = cy - (by1 + sh / 2) * scale
        return lambda x: x * scale + ox, lambda y: y * scale + oy, scale

    tx_a, ty_a, scale_a = _make_transform(before, a_center_x, a_center_y)
    tx_b, ty_b, scale_b = _make_transform(after, b_center_x, b_center_y)

    # Fold line color
    fold_color = "#E74C3C" if fold_type == "mountain_fold" else "#3B82F6" if fold_type == "valley_fold" else "#8B7355"
    fold_label = {
        "valley_fold": "valley",
        "mountain_fold": "mountain",
        "cut": "cut",
    }.get(fold_type, "fold")

    lines = []
    lines.append(f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">')
    lines.append(f'  <rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#FFF9F0"/>')

    # ── A side (before) ──
    lines.append(f'  <text x="{a_center_x}" y="22" text-anchor="middle" font-size="10" fill="#999" font-weight="600">A</text>')
    for i, layer in enumerate(before.layers):
        shadow_path = _polygon_to_svg_path(layer, lambda x: tx_a(x) + 2, lambda y: ty_a(y) + 2)
        lines.append(f'  <path d="{shadow_path}" fill="#E8D5C0" opacity="0.3"/>')
        path = _polygon_to_svg_path(layer, tx_a, ty_a)
        fill = "#FFE8E8" if i == 0 else "#FFFEF5"
        lines.append(f'  <path d="{path}" fill="{fill}" stroke="#8B7355" stroke-width="1.5"/>')

    # Draw fold line on A side
    if fold_line:
        fl_x1 = tx_a(fold_line[0][0])
        fl_y1 = ty_a(fold_line[0][1])
        fl_x2 = tx_a(fold_line[1][0])
        fl_y2 = ty_a(fold_line[1][1])
        lines.append(f'  <line x1="{fl_x1:.1f}" y1="{fl_y1:.1f}" x2="{fl_x2:.1f}" y2="{fl_y2:.1f}" stroke="{fold_color}" stroke-width="2" stroke-dasharray="6,4"/>')

        # Action arrow perpendicular to fold line
        mid_x = (fl_x1 + fl_x2) / 2
        mid_y = (fl_y1 + fl_y2) / 2
        dx = fl_x2 - fl_x1
        dy = fl_y2 - fl_y1
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            nx, ny = -dy / length * 20, dx / length * 20
            lines.append(
                f'  <path d="M {mid_x:.1f} {mid_y:.1f} Q {mid_x + nx:.1f} {mid_y + ny:.1f} '
                f'{mid_x + nx * 0.5:.1f} {mid_y + ny * 1.5:.1f}" '
                f'fill="none" stroke="#10B981" stroke-width="2"/>'
            )
            lines.append(f'  <circle cx="{mid_x + nx * 0.5:.1f}" cy="{mid_y + ny * 1.5:.1f}" r="3" fill="#10B981"/>')

    # ── Arrow between A and B ──
    lines.append(f'  <path d="M 163 115 L 178 115" fill="none" stroke="#666" stroke-width="2.5"/>')
    lines.append(f'  <polygon points="176,110 186,115 176,120" fill="#666"/>')

    # ── B side (after) ──
    lines.append(f'  <text x="{b_center_x}" y="22" text-anchor="middle" font-size="10" fill="#8B7355" font-weight="700">B</text>')
    for i, layer in enumerate(after.layers):
        shadow_path = _polygon_to_svg_path(layer, lambda x: tx_b(x) + 2, lambda y: ty_b(y) + 2)
        lines.append(f'  <path d="{shadow_path}" fill="#E8D5C0" opacity="0.3"/>')
        path = _polygon_to_svg_path(layer, tx_b, ty_b)
        fill = "#FFFEF5" if i == 0 else "#F5F0E8"
        opacity = max(0.4, 1.0 - i * 0.2)
        lines.append(f'  <path d="{path}" fill="{fill}" stroke="#8B7355" stroke-width="1.5" opacity="{opacity}"/>')

    # ── Action label ──
    if action_label:
        lines.append(f'  <text x="{width // 2}" y="{height - 28}" text-anchor="middle" font-size="11" fill="#10B981" font-weight="600">{action_label}</text>')

    # ── Legend ──
    ly = height - 12
    lines.append(f'  <line x1="20" y1="{ly}" x2="40" y2="{ly}" stroke="{fold_color}" stroke-width="1.5" stroke-dasharray="6,4"/>')
    lines.append(f'  <text x="45" y="{ly + 4}" font-size="9" fill="#666">{fold_label}</text>')
    lines.append(f'  <line x1="100" y1="{ly}" x2="120" y2="{ly}" stroke="#10B981" stroke-width="2"/>')
    lines.append(f'  <text x="125" y="{ly + 4}" font-size="9" fill="#666">action</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ── Tutorial Builder ────────────────────────────────────────────────────────

def build_tutorial_svgs(fold_ops: list[dict], paper_size: float = 1.0) -> list[str]:
    """
    Given a list of fold operations from the LLM, simulate each step
    and render before→after SVG diagrams.

    Each fold_op dict should have:
      - type: "valley_fold", "mountain_fold", "cut", "flip", "rotate"
      - fold_line: [[x1,y1], [x2,y2]]  (in 0-1 coordinates)
      - fold_side: "bottom", "top", "left", "right" (which side folds)
      - label: action label text (optional)
    """
    paper = PaperState(paper_size)
    svgs = []

    for op in fold_ops:
        op_type = op.get("type", "valley_fold")
        fold_line_raw = op.get("fold_line", [[0, 0.5], [1, 0.5]])
        fold_side = op.get("fold_side", "bottom")
        label = op.get("label", "")

        fold_line = (
            (fold_line_raw[0][0], fold_line_raw[0][1]),
            (fold_line_raw[1][0], fold_line_raw[1][1]),
        )

        before = paper.clone()

        if op_type in ("valley_fold", "mountain_fold"):
            paper.valley_fold(fold_line[0], fold_line[1], fold_side)
        elif op_type == "cut":
            keep = op.get("keep_side", "left")
            paper.cut(fold_line[0], fold_line[1], keep)

        after = paper.clone()

        svg = render_step_svg(
            before=before,
            after=after,
            fold_line=fold_line,
            fold_type=op_type,
            action_label=label,
        )
        svgs.append(svg)

    return svgs
