"""Quick test of the paper folding engine."""
from integrations.paper_engine import PaperState, build_tutorial_svgs

ops = [
    {"type": "valley_fold", "fold_line": [[0, 0], [1, 1]], "fold_side": "right", "label": "Presavij dijagonalno"},
    {"type": "valley_fold", "fold_line": [[0, 0.5], [0.5, 0]], "fold_side": "right", "label": "Presavij ugao"},
]
svgs = build_tutorial_svgs(ops)
print(f"Generated {len(svgs)} SVG diagrams")
for i, svg in enumerate(svgs):
    print(f"Step {i+1}: {len(svg)} chars")
    with open(f"data/fold/test_step_{i+1}.svg", "w") as f:
        f.write(svg)
print("Saved to data/fold/test_step_1.svg and test_step_2.svg")
