"""Layer 1: deterministic checks over a trace.

These are the cheap, reproducible verdicts. Nothing here calls a model, so the
same trace always produces the same result, which is what makes this the layer
the other two get measured against.

Five checks, each applied only where it means something:

  route     did the router pick the source the task expects
  answer    do the required facts appear in the answer
  decline   did the agent refuse instead of inventing
  latency   did the run finish inside the budget for its route
  error     did any node fail, including the state error that run_agent_sync
            would have swallowed

A check that does not apply to a task is recorded as "not applicable" rather
than silently passing, because a task that is never actually checked should be
visible as such.
"""

import re

from agent_loop.tasks import answer_matches

# Budgets are generous multiples of the pilot's observed per route latency
# (direct 1.9s, retrieval 3.6s, web search 6.4s). They are here to catch a
# hang or a retry storm, not to grade speed.
LATENCY_BUDGET_MS = {
    "direct": 10_000,
    "retrieval": 15_000,
    "web_search": 25_000,
    "blocked": 5_000,
}
DEFAULT_LATENCY_BUDGET_MS = 20_000

# Phrases that mark a refusal or a stated gap in the evidence. Matching is on
# normalised text. This is a heuristic and is meant to be: layers 2 and 3 exist
# because a regex cannot tell a genuine decline from a fluent evasion.
_DECLINE_PATTERNS = (
    r"\bdo(?:es)? not (?:contain|mention|specify|state|provide|include|give|cover|report|list)\b",
    r"\bdon'?t (?:contain|mention|specify|state|provide|include|have)\b",
    r"\bis not (?:mentioned|specified|stated|provided|included|available|covered|listed)\b",
    r"\bare not (?:mentioned|specified|stated|provided|included|available|covered|listed)\b",
    r"\bno (?:information|details|mention|data|figure|record|reference)\b",
    r"\bnot (?:available|found|present) in\b",
    r"\bcannot (?:answer|provide|determine|confirm|verify|share|access)\b",
    r"\bcan'?t (?:answer|provide|determine|confirm|verify|share|access)\b",
    r"\bunable to (?:answer|provide|determine|confirm|find|access)\b",
    r"\bi (?:do not|don'?t) have (?:access|information|any)\b",
    r"\bnot (?:covered|addressed) (?:in|by)\b",
    r"\binsufficient (?:information|context|evidence)\b",
    r"\bthe (?:context|documents?|sources?) (?:do(?:es)? not|lack)\b",
)
_DECLINE_RE = re.compile("|".join(_DECLINE_PATTERNS), re.IGNORECASE)

NOT_APPLICABLE = "not_applicable"


def declines(text: str) -> tuple[bool, list[str]]:
    """Whether an answer refuses or states that the evidence is missing."""
    matches = [m.group(0).lower() for m in _DECLINE_RE.finditer(text or "")]
    return bool(matches), sorted(set(matches))


def latency_budget_ms(route: str | None) -> int:
    return LATENCY_BUDGET_MS.get(route or "", DEFAULT_LATENCY_BUDGET_MS)


def check_trace(trace: dict, task: dict) -> dict:
    """Apply every applicable rule to one trace."""
    checks: dict[str, dict] = {}
    answer = trace.get("answer") or ""
    route = trace.get("route_decision")

    # route
    if task["expected_route"] is not None:
        checks["route"] = {
            "applicable": True,
            "passed": route == task["expected_route"],
            "expected": task["expected_route"],
            "actual": route,
        }
    else:
        checks["route"] = {"applicable": False, "reason": NOT_APPLICABLE}

    # answer
    if task["expected_answer"] is not None:
        matched, missing = answer_matches(task["expected_answer"], answer)
        checks["answer"] = {
            "applicable": True,
            "passed": matched,
            "missing_groups": missing,
        }
    else:
        checks["answer"] = {"applicable": False, "reason": NOT_APPLICABLE}

    # decline
    if task["category"] == "unanswerable_decline":
        declined, phrases = declines(answer)
        checks["decline"] = {
            "applicable": True,
            "passed": declined,
            "matched_phrases": phrases,
        }
    else:
        checks["decline"] = {"applicable": False, "reason": NOT_APPLICABLE}

    # latency
    budget = latency_budget_ms(route)
    latency = trace.get("latency_ms", 0.0)
    checks["latency"] = {
        "applicable": True,
        "passed": latency <= budget,
        "latency_ms": latency,
        "budget_ms": budget,
    }

    # error
    state_error = trace.get("state_error")
    invoke_exception = trace.get("invoke_exception")
    checks["error"] = {
        "applicable": True,
        "passed": not (state_error or invoke_exception),
        "state_error": state_error,
        "invoke_exception": invoke_exception,
    }

    failed = [
        name for name, check in checks.items() if check["applicable"] and not check["passed"]
    ]
    return {
        "task_id": task["id"],
        "category": task["category"],
        "checks": checks,
        "failure_tags": failed,
        "rule_pass": not failed,
    }


def rule_label(result: dict) -> bool:
    """The single pass or fail this layer contributes to agreement analysis."""
    return result["rule_pass"]
