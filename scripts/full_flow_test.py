"""
MakeItAi - Full Flow Simulation
Simulates a user going through all 4 phases and generates a report.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.graph import agent

REPORT_PATH = PROJECT_ROOT / "scripts" / "flow_report.txt"


def run_chat(message, history=None):
    """Run a single chat interaction."""
    start = time.time()
    result = agent.invoke({
        "user_message": message,
        "current_phase": "MASTER",
        "project_context": {},
        "conversation_history": history or [],
        "response": "",
        "sources": [],
        "inspiration_images": [],
    })
    elapsed = round(time.time() - start, 2)
    return result, elapsed


def safe_text(text, max_len=500):
    """Truncate and make text ASCII-safe for report."""
    return text[:max_len].encode("ascii", "replace").decode()


def main():
    lines = []
    total_start = time.time()

    def log(text=""):
        print(text)
        lines.append(text)

    log("=" * 70)
    log("  MakeItAi - FULL FLOW SIMULATION REPORT")
    log(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    # ── PHASE 1: SCOUT ───────────────────────────────────────────────
    log("\n" + "-" * 70)
    log("  PHASE 1: SCOUT (Market Research & Inspiration)")
    log("-" * 70)

    msg1 = "I have paper, scissors, and glue. What can I make to sell on Etsy?"
    log(f"\n[USER]: {msg1}")
    result1, t1 = run_chat(msg1)
    log(f"[AGENT PHASE]: {result1['current_phase']}")
    log(f"[RESPONSE TIME]: {t1}s")
    log(f"[INSPIRATION IMAGES]: {len(result1.get('inspiration_images', []))} images")
    for img in result1.get("inspiration_images", [])[:3]:
        log(f"  - {safe_text(img.get('description', 'No description'), 80)}")
    log(f"[RESPONSE]:\n{safe_text(result1['response'])}")

    phase1_ok = result1["current_phase"] == "SCOUT"
    images_ok = len(result1.get("inspiration_images", [])) > 0
    history = result1["conversation_history"]

    # ── PHASE 2: MASTER (Technical Guidance via RAG) ─────────────────
    log("\n" + "-" * 70)
    log("  PHASE 2: MASTER (Technical Guidance - RAG)")
    log("-" * 70)

    msg2 = "How do I make a paper flower step by step?"
    log(f"\n[USER]: {msg2}")
    result2, t2 = run_chat(msg2, history)
    log(f"[AGENT PHASE]: {result2['current_phase']}")
    log(f"[RESPONSE TIME]: {t2}s")
    log(f"[RAG SOURCES]: {len(result2['sources'])} documents retrieved")
    for src in result2["sources"][:3]:
        log(f"  - similarity: {src['similarity']:.3f} | {safe_text(src['metadata'].get('source', ''), 50)}")
    log(f"[RESPONSE]:\n{safe_text(result2['response'])}")

    phase2_ok = result2["current_phase"] == "MASTER"
    rag_ok = len(result2["sources"]) > 0
    history = result2["conversation_history"]

    # ── PHASE 3: TROUBLESHOOTER (Problem Analysis) ───────────────────
    log("\n" + "-" * 70)
    log("  PHASE 3: TROUBLESHOOTER (Problem Diagnosis)")
    log("-" * 70)

    msg3 = "The petals keep falling off and the glue isn't holding. What am I doing wrong?"
    log(f"\n[USER]: {msg3}")
    result3, t3 = run_chat(msg3, history)
    log(f"[AGENT PHASE]: {result3['current_phase']}")
    log(f"[RESPONSE TIME]: {t3}s")
    log(f"[RESPONSE]:\n{safe_text(result3['response'])}")

    phase3_ok = result3["current_phase"] == "TROUBLESHOOTER"
    history = result3["conversation_history"]

    # ── PHASE 4: MERCHANT (Etsy Listing) ─────────────────────────────
    log("\n" + "-" * 70)
    log("  PHASE 4: MERCHANT (Etsy Listing Generation)")
    log("-" * 70)

    msg4 = "I finished making 10 paper flower bouquets. Help me create an Etsy listing. They are made from crepe paper, each bouquet has 5 flowers, 30cm tall, colors: pink, white, yellow."
    log(f"\n[USER]: {msg4}")
    result4, t4 = run_chat(msg4, history)
    log(f"[AGENT PHASE]: {result4['current_phase']}")
    log(f"[RESPONSE TIME]: {t4}s")
    log(f"[RESPONSE]:\n{safe_text(result4['response'], 800)}")

    phase4_ok = result4["current_phase"] == "MERCHANT"

    # ── SUMMARY ──────────────────────────────────────────────────────
    total_time = round(time.time() - total_start, 2)

    log("\n" + "=" * 70)
    log("  SUMMARY")
    log("=" * 70)

    checks = [
        ("SCOUT routing", phase1_ok),
        ("Pexels mood board images", images_ok),
        ("MASTER routing", phase2_ok),
        ("RAG sources retrieved", rag_ok),
        ("TROUBLESHOOTER routing", phase3_ok),
        ("MERCHANT routing", phase4_ok),
    ]

    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        log(f"  [{status}] {name}")

    passed = sum(1 for _, ok in checks if ok)
    log(f"\n  Result: {passed}/{len(checks)} checks passed")
    log(f"  Total time: {total_time}s")
    log(f"  Avg response time: {round((t1+t2+t3+t4)/4, 2)}s")
    log("=" * 70)

    # Save report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
