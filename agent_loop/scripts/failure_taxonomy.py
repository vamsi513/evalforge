"""Cluster development failures into a taxonomy built from the traces.

Usage:
    python -m agent_loop.scripts.failure_taxonomy --label dev_baseline

The failure set is the union of what layer 1 marked failing and what the human
marked failing on the rows they labelled. Taking the union rather than the rule
verdict alone matters: if the taxonomy were built from rule failures only, every
failure the rules cannot see would be invisible to the analysis that chooses the
fix, which is the mistake this whole exercise is meant to avoid.

Clusters are assigned from trace evidence, not from a label. The distinction
that does most of the work is whether the fact the answer was missing is
present in the passages the agent was actually shown:

  retrieval_miss              the fact is not in the retrieved context, so the
                              agent could not have used it
  ignored_retrieved_evidence  the fact is in the retrieved context and the
                              answer still does not state it

Those two look identical in an accuracy number and need completely different
fixes, which is why they are separated here.

Writes results/agent_loop/failure_taxonomy.md and a JSON companion.
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "agent_loop"

EXCERPTS_PER_CLUSTER = 3
_EXCERPT_CHARS = 300

CLUSTER_DESCRIPTIONS = {
    "error_handling": (
        "A node failed. The graph state carries an error, or the invocation raised."
    ),
    "wrong_tool": (
        "The router chose a source the task did not call for, so the rest of the run "
        "was working from the wrong kind of evidence."
    ),
    "failure_to_decline": (
        "The question could not be answered from the evidence and the agent answered "
        "anyway, instead of saying so or correcting the premise. Where "
        "`missed_by_decline_rule` is set, layer 1 passed the row because refusal "
        "phrasing appeared somewhere in the answer while the answer still supplied "
        "the information: the detector failed, not just the agent."
    ),
    "retrieval_miss": (
        "The route was right and the agent behaved sensibly, but the passage holding "
        "the required fact was never retrieved, so the agent reported that its context "
        "did not contain the answer. The fact is in the corpus."
    ),
    "ignored_retrieved_evidence": (
        "The required fact was present in the passages the agent was shown, and the "
        "answer still failed to state it."
    ),
    "direct_answer_error": (
        "No retrieval involved. The agent answered from its own knowledge and got it "
        "wrong."
    ),
    "unverifiable_live_answer": (
        "A live web question where the answer cannot be checked against anything in "
        "the trace, or the agent returned conflicting values."
    ),
}


def classify(trace: dict, task: dict, rule: dict) -> tuple[str, dict]:
    """Assign one cluster from the trace, with the evidence that decided it."""
    from agent_loop.tasks import term_present

    if trace.get("invoke_exception") or trace.get("state_error"):
        return "error_handling", {
            "state_error": trace.get("state_error"),
            "invoke_exception": trace.get("invoke_exception"),
        }

    route_check = rule["checks"]["route"]
    if route_check["applicable"] and not route_check["passed"]:
        return "wrong_tool", {
            "expected_route": route_check["expected"],
            "actual_route": route_check["actual"],
        }

    decline_check = rule["checks"]["decline"]
    if decline_check["applicable"] and not decline_check["passed"]:
        return "failure_to_decline", {"route": trace.get("route_decision")}

    answer_check = rule["checks"]["answer"]
    if answer_check["applicable"] and not answer_check["passed"]:
        missing = answer_check["missing_groups"]
        context = trace.get("context") or ""
        present_in_context = [
            group for group in missing if any(term_present(t, context) for t in group)
        ]
        evidence = {
            "missing_groups": missing,
            "missing_but_present_in_retrieved_context": present_in_context,
            "retrieved_titles": trace.get("retrieved_titles", []),
            "retrieval_score": trace.get("retrieval_score"),
        }
        if trace.get("route_decision") == "direct":
            return "direct_answer_error", evidence
        if present_in_context:
            return "ignored_retrieved_evidence", evidence
        return "retrieval_miss", evidence

    # No rule check failed, so this entered the set because a human marked it
    # failing. What the rules missed is the interesting part.
    if task["category"] == "unanswerable_decline":
        # The decline regex matched refusal phrasing somewhere in the answer, so
        # layer 1 passed it, and the answer supplied the information anyway.
        # This is still a failure to decline; it is the detector that failed.
        return "failure_to_decline", {
            "route": trace.get("route_decision"),
            "missed_by_decline_rule": True,
            "matched_phrases": rule["checks"]["decline"].get("matched_phrases", []),
        }
    if trace.get("route_decision") == "web_search":
        return "unverifiable_live_answer", {
            "sources_returned": len(trace.get("sources") or []),
            "route": trace.get("route_decision"),
        }
    return "direct_answer_error", {"note": "no rule check failed; human marked it failing"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="dev_baseline")
    args = parser.parse_args()

    from agent_loop.review_sheet import human_label, load_human_labels
    from agent_loop.tasks import load_tasks

    traces = {
        p.stem: json.loads(p.read_text())
        for p in sorted((RESULTS_DIR / "traces" / args.label).glob("*.json"))
    }
    rules = {
        r["task_id"]: r
        for r in json.loads((RESULTS_DIR / "scores" / f"{args.label}_rules.json").read_text())[
            "results"
        ]
    }
    judge_path = RESULTS_DIR / "scores" / f"{args.label}_judge.json"
    judge = {
        j["task_id"]: j for j in json.loads(judge_path.read_text())["judgments"]
    } if judge_path.exists() else {}

    review_path = RESULTS_DIR / "review" / f"{args.label}_review.csv"
    human: dict[str, bool | None] = {}
    if review_path.exists():
        loaded = load_human_labels(review_path)
        human = {run_id: human_label(entry) for run_id, entry in loaded["labels"].items()}

    tasks_by_id = {task["id"]: task for task in load_tasks()}

    failing = sorted(
        {task_id for task_id, r in rules.items() if not r["rule_pass"]}
        | {task_id for task_id, label in human.items() if label is False}
    )

    clusters: dict[str, list[dict]] = defaultdict(list)
    for task_id in failing:
        trace, task, rule = traces[task_id], tasks_by_id[task_id], rules[task_id]
        cluster, evidence = classify(trace, task, rule)
        clusters[cluster].append(
            {
                "task_id": task_id,
                "category": task["category"],
                "question": task["question"],
                "route": trace.get("route_decision"),
                "answer_excerpt": (trace.get("answer") or "")[:_EXCERPT_CHARS],
                "evidence": evidence,
                "caught_by_rule": not rule["rule_pass"],
                "rule_tags": rule["failure_tags"],
                "caught_by_judge": (
                    None if task_id not in judge else not judge[task_id]["judge_passed"]
                ),
                "human_pass": human.get(task_id),
            }
        )

    ordered = sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    detection = {}
    for name, members in ordered:
        judged = [m for m in members if m["caught_by_judge"] is not None]
        reviewed = [m for m in members if m["human_pass"] is not None]
        detection[name] = {
            "total": len(members),
            "caught_by_rules": sum(1 for m in members if m["caught_by_rule"]),
            "judged": len(judged),
            "caught_by_judge": sum(1 for m in judged if m["caught_by_judge"]),
            "human_reviewed": len(reviewed),
            "human_called_fail": sum(1 for m in reviewed if m["human_pass"] is False),
        }

    payload = {
        "label": args.label,
        "built_at": datetime.now(UTC).isoformat(),
        "development_tasks": len(traces),
        "failures": len(failing),
        "failure_ids": failing,
        "failure_set_definition": (
            "Union of layer 1 rule failures across all development tasks and human "
            "failures on the subset that was labelled."
        ),
        "cluster_counts": {name: len(members) for name, members in ordered},
        "by_category": {
            name: dict(Counter(m["category"] for m in members)) for name, members in ordered
        },
        "detection_by_layer": detection,
        "clusters": {name: members for name, members in ordered},
    }
    (RESULTS_DIR / "failure_taxonomy.json").write_text(json.dumps(payload, indent=2) + "\n")
    _write_markdown(payload, ordered, RESULTS_DIR / "failure_taxonomy.md")

    print(f"{len(failing)} failures across {len(traces)} development tasks")
    for name, members in ordered:
        counts = detection[name]
        print(
            f"  {name:<28}{counts['total']:>3}   "
            f"rules {counts['caught_by_rules']}/{counts['total']}   "
            f"judge {counts['caught_by_judge']}/{counts['judged']}   "
            f"human {counts['human_called_fail']}/{counts['human_reviewed']}"
        )
    print(f"\nwrote {RESULTS_DIR / 'failure_taxonomy.md'}")


def _write_markdown(payload: dict, ordered, path: Path) -> None:
    lines: list[str] = []
    add = lines.append

    add("# Development failure taxonomy")
    add("")
    add(
        f"{payload['failures']} failures across {payload['development_tasks']} development "
        f"tasks, from the `{payload['label']}` run."
    )
    add("")
    add(payload["failure_set_definition"])
    add("")
    add(
        "Clusters are assigned from trace evidence. The decisive test for a missing "
        "fact is whether that fact appears in the passages the agent was actually "
        "shown, which separates a retrieval problem from a generation problem."
    )
    add("")

    add("## Counts")
    add("")
    add("| Cluster | Failures | Caught by rules | Caught by judge | Human called fail |")
    add("|---|---|---|---|---|")
    for name, _members in ordered:
        d = payload["detection_by_layer"][name]
        add(
            f"| `{name}` | {d['total']} | {d['caught_by_rules']}/{d['total']} | "
            f"{d['caught_by_judge']}/{d['judged']} | "
            f"{d['human_called_fail']}/{d['human_reviewed']} |"
        )
    add("")
    add(
        "Judge and human columns are over the subset each layer actually saw: every "
        "failure was judged, but only the 40 row review sample was labelled."
    )
    add("")

    for name, members in ordered:
        add(f"## {name} ({len(members)})")
        add("")
        add(CLUSTER_DESCRIPTIONS.get(name, ""))
        add("")
        by_cat = payload["by_category"][name]
        add(f"By category: {', '.join(f'{k} {v}' for k, v in sorted(by_cat.items()))}")
        add("")
        add(f"Task ids: {', '.join(m['task_id'] for m in members)}")
        add("")
        for member in members[:EXCERPTS_PER_CLUSTER]:
            add(f"### `{member['task_id']}`")
            add("")
            add(f"**Question.** {member['question']}")
            add("")
            add(f"**Route taken.** `{member['route']}`")
            add("")
            add("**Answer excerpt.**")
            add("")
            excerpt = member["answer_excerpt"].replace("\n", " ").strip()
            add(f"> {excerpt}")
            add("")
            evidence = member["evidence"]
            if "missing_groups" in evidence:
                missing = "; ".join(" or ".join(g) for g in evidence["missing_groups"])
                add(f"**Required but absent from the answer.** {missing}")
                add("")
                in_context = evidence["missing_but_present_in_retrieved_context"]
                if in_context:
                    shown = "; ".join(" or ".join(g) for g in in_context)
                    add(
                        f"**Was it in the retrieved passages?** Yes: {shown}. "
                        "The agent had it and did not use it."
                    )
                else:
                    add(
                        "**Was it in the retrieved passages?** No. The agent could not "
                        "have answered from what it was given."
                    )
                add("")
                titles = evidence.get("retrieved_titles") or []
                if titles:
                    add(f"**Documents retrieved.** {', '.join(titles)}")
                    add("")
            elif evidence:
                add(f"**Evidence.** `{json.dumps(evidence)}`")
                add("")
        if len(members) > EXCERPTS_PER_CLUSTER:
            add(f"_{len(members) - EXCERPTS_PER_CLUSTER} further case(s) in the JSON companion._")
            add("")

    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
