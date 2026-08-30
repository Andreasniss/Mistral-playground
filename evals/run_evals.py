"""Run deterministic routing and grounding checks without credentials."""

from __future__ import annotations

import json
from pathlib import Path

from showcase import run_showcase


def evaluate() -> tuple[int, list[dict]]:
    cases = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        actual = run_showcase(case["prompt"])
        checks = {
            "route": actual.route == case["expected_route"],
            "tool": actual.tool == case["expected_tool"],
            "grounding": all(term.lower() in actual.answer.lower() for term in case["required_terms"]),
        }
        results.append({"id": case["id"], "passed": all(checks.values()), "checks": checks})
    return sum(item["passed"] for item in results), results


if __name__ == "__main__":
    passed, results = evaluate()
    print(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=2))
    raise SystemExit(0 if passed == len(results) else 1)
