"""
Runs every case in evals/cases.json against a running /triage endpoint and
scores it on the key field (category). Prints which cases failed so you
can look at them.

Usage:
    python evals/run_eval.py                 # against http://localhost:8000
    python evals/run_eval.py --url http://localhost:8000
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

CASES_PATH = Path(__file__).parent / "cases.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()

    cases = json.loads(CASES_PATH.read_text())

    correct = 0
    failures = []

    for case in cases:
        try:
            resp = httpx.post(f"{args.url}/triage", json={"text": case["text"]}, timeout=60.0)
        except httpx.RequestError as exc:
            failures.append((case, f"request failed: {exc}"))
            continue

        if resp.status_code != 200:
            failures.append((case, f"HTTP {resp.status_code}: {resp.text}"))
            continue

        body = resp.json()
        got = body.get("category")
        expected = case["expected_category"]

        if got == expected:
            correct += 1
        else:
            failures.append((case, f"expected '{expected}', got '{got}' (full response: {body})"))

    total = len(cases)
    print(f"\nScore: {correct}/{total} correct on category\n")

    if failures:
        print("Failures:")
        for case, reason in failures:
            print(f"  #{case['id']} \"{case['text']}\" — {reason}")
    else:
        print("All cases passed.")

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()