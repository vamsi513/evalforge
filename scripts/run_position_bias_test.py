"""
scripts/run_position_bias_test.py — Position-bias test for the local judge.

For each hand-authored pair in evaluation/position_bias_pairs.json (a prompt
plus a genuinely better and genuinely worse response), asks the local Ollama
judge which response is better twice: once in the original order (better
response presented as "A"), once with the order swapped (better response
presented as "B"). If the judge is free of position bias, it should prefer
the actually-better response both times, regardless of which letter it was
assigned. A pair "flips" if the judge's verdict tracks the letter/position
instead of the actual content quality.

This is a separate comparative-judging path from the pointwise scoring judge
in app/engine/judge.py -- pairwise "which is better" is a different task
shape, not a variant of the existing score-one-answer flow.

Usage:
    python -m scripts.run_position_bias_test
    python -m scripts.run_position_bias_test --out results.json

Runs entirely against the local Ollama server -- no paid API calls, no cost.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

_PAIRS_PATH = Path(__file__).parent.parent / "evaluation" / "position_bias_pairs.json"

_SYSTEM_PROMPT = (
    "You are comparing two candidate answers to the same question. "
    "Decide which one is a better answer -- more accurate, complete, and helpful. "
    "Respond with only JSON matching the schema."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "preferred": {"type": "string", "enum": ["A", "B"]},
        "reasoning": {"type": "string"},
    },
    "required": ["preferred", "reasoning"],
    "additionalProperties": False,
}


def _user_prompt(prompt: str, response_a: str, response_b: str) -> str:
    return (
        f"Question:\n{prompt}\n\n"
        f"Response A:\n{response_a}\n\n"
        f"Response B:\n{response_b}\n\n"
        "Which response is better, A or B?"
    )


def _compare(prompt: str, response_a: str, response_b: str) -> dict[str, Any]:
    payload = {
        "model": settings.judge_model_ollama,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(prompt, response_a, response_b)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "position_bias_verdict", "schema": _SCHEMA},
        },
    }
    with httpx.Client(base_url=settings.ollama_base_url, timeout=120.0) as client:
        response = client.post("/v1/chat/completions", json=payload)
        response.raise_for_status()
        body = response.json()
    content = body["choices"][0]["message"]["content"]
    # Ollama occasionally wraps structured output in prose despite the
    # schema; extract the first JSON object rather than assuming a clean
    # payload, matching the defensive parsing the pointwise judge doesn't
    # need (it goes through the same json_schema mode but this is a second,
    # independent code path worth not trusting blindly).
    match = re.search(r"\{.*\}", content, re.DOTALL)
    parsed = json.loads(match.group(0) if match else content)
    return parsed


def run() -> list[dict[str, Any]]:
    with open(_PAIRS_PATH) as f:
        pairs = json.load(f)["pairs"]

    results = []
    for i, pair in enumerate(pairs):
        prompt = pair["prompt"]
        better = pair["response_better"]
        worse = pair["response_worse"]

        # Original order: better response is "A".
        normal = _compare(prompt, better, worse)
        normal_correct = normal["preferred"] == "A"

        # Swapped order: better response is "B".
        swapped = _compare(prompt, worse, better)
        swapped_correct = swapped["preferred"] == "B"

        flipped = normal_correct != swapped_correct
        results.append({
            "index": i,
            "prompt": prompt,
            "normal_preferred": normal["preferred"],
            "normal_correct": normal_correct,
            "swapped_preferred": swapped["preferred"],
            "swapped_correct": swapped_correct,
            "flipped": flipped,
        })
        print(
            f"[{i}] normal={normal['preferred']}({'ok' if normal_correct else 'WRONG'}) "
            f"swapped={swapped['preferred']}({'ok' if swapped_correct else 'WRONG'}) "
            f"{'FLIPPED' if flipped else 'consistent'} | {prompt[:50]}"
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    results = run()
    n = len(results)
    flipped = sum(1 for r in results if r["flipped"])
    normal_acc = sum(1 for r in results if r["normal_correct"]) / n
    swapped_acc = sum(1 for r in results if r["swapped_correct"]) / n

    print("\n" + "=" * 60)
    print(f"Pairs tested: {n}")
    print(f"Position-bias rate (verdict flips on swap): {flipped}/{n} ({flipped / n:.1%})")
    print(f"Accuracy picking the better response, normal order: {normal_acc:.1%}")
    print(f"Accuracy picking the better response, swapped order: {swapped_acc:.1%}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({
                "n_pairs": n,
                "flipped_count": flipped,
                "position_bias_rate": round(flipped / n, 4),
                "normal_order_accuracy": round(normal_acc, 4),
                "swapped_order_accuracy": round(swapped_acc, 4),
                "results": results,
            }, f, indent=2)
        print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()
