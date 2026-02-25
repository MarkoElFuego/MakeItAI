"""
Test script for LangGraph orchestrator routing logic.
Tests that different user messages get routed to the correct phase.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.graph import agent


def test_message(message: str, expected_phase: str):
    """Send a message through the agent and check the routed phase."""
    print(f"\n{'='*60}")
    print(f"MESSAGE:  {message}")
    print(f"EXPECTED: {expected_phase}")

    result = agent.invoke({
        "user_message": message,
        "current_phase": "MASTER",
        "project_context": {},
        "conversation_history": [],
        "response": "",
        "sources": [],
    })

    phase = result["current_phase"]
    response = result["response"][:150]
    match = "OK" if phase == expected_phase else "MISMATCH"

    print(f"GOT:      {phase}  [{match}]")
    print(f"RESPONSE: {response.encode('ascii', 'replace').decode()}...")
    print(f"SOURCES:  {len(result['sources'])} documents")
    return phase == expected_phase


if __name__ == "__main__":
    test_cases = [
        ("What should I make to sell on Etsy?", "SCOUT"),
        ("How do I make a wooden cutting board?", "MASTER"),
        ("My wood joint has a gap, what went wrong?", "TROUBLESHOOTER"),
        ("I finished my product, help me create an Etsy listing", "MERCHANT"),
        ("What crafts are trending right now?", "SCOUT"),
        ("How to apply wood stain properly?", "MASTER"),
    ]

    passed = 0
    total = len(test_cases)

    for message, expected in test_cases:
        if test_message(message, expected):
            passed += 1

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed}/{total} passed")
    if passed == total:
        print("All routing tests passed!")
    else:
        print(f"{total - passed} test(s) had unexpected routing.")
