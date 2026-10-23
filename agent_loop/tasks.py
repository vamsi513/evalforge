"""Task schema, loader and normalised answer matching.

A task is one line of agent_loop/data/tasks.jsonl. Every task carries at least
one check: an expected route, a checkable expected answer, or an explicit
expected behaviour. The loader refuses a file where that is not true, because a
task with nothing to check would silently count as a pass later on.

Answer matching is deliberately blunt. `expected_answer.required` is a list of
groups; a group is satisfied when any one of its surface forms appears in the
answer, and the answer matches when every group is satisfied. That keeps "10,000x"
and "10000 times" from being scored as different answers, without pretending a
regex understands the sentence. Layers 2 and 3 exist for the part this cannot see.
"""

import json
import re
import unicodedata
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
TASKS_PATH = DATA_DIR / "tasks.jsonl"

CATEGORIES = (
    "tool_selection",
    "multi_step_retrieval",
    "direct_no_tools",
    "unanswerable_decline",
)

# The routes AgentIQ's router may emit. Mirrors agent/state.py's ALLOWED_ROUTES.
# Kept as a literal rather than imported so this module can be loaded, and the
# task file validated, without AgentIQ on the path.
ROUTES = ("retrieval", "web_search", "direct")

REQUIRED_FIELDS = (
    "id",
    "category",
    "question",
    "expected_route",
    "expected_answer",
    "expected_behavior",
    "must_not_contain",
    "source_docs",
)

# Terms at or below this length, and purely numeric terms, are matched on word
# boundaries. Without that, the required term "8" would be satisfied by "48".
_SHORT_TERM_CHARS = 3


def _normalise(text: str) -> str:
    """Lowercase, fold dash and quote variants, collapse whitespace.

    The corpus uses em dashes and typographic quotes, and a model's answer may
    use either those or their ASCII equivalents. Folding both sides means a
    match does not turn on which one came back.
    """
    folded = unicodedata.normalize("NFKC", text).lower()
    folded = re.sub(r"[‐-―−]", "-", folded)
    folded = re.sub(r"[‘’‛]", "'", folded)
    folded = re.sub(r"[“”]", '"', folded)
    return re.sub(r"\s+", " ", folded).strip()


# "77 million" and "77m" are the same quantity. Folding them is a general
# normalisation, like the digit separators above, not a per task allowance.
_MAGNITUDE_WORDS = {"thousand": "k", "million": "m", "billion": "b", "trillion": "t"}
_MAGNITUDE_RE = re.compile(
    r"(?<=\d)\s*(" + "|".join(_MAGNITUDE_WORDS) + r")\b", re.IGNORECASE
)


def _strip_separators(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def _fold_magnitudes(text: str) -> str:
    return _MAGNITUDE_RE.sub(lambda m: _MAGNITUDE_WORDS[m.group(1).lower()], text)


def _variants(text: str) -> set[str]:
    """Every equivalent spelling of one piece of text."""
    base = _normalise(text)
    forms = {base, _strip_separators(base)}
    forms |= {_fold_magnitudes(form) for form in list(forms)}
    return {form for form in forms if form}


def _haystacks(text: str) -> set[str]:
    """The answer in each of its equivalent spellings."""
    return _variants(text)


def term_present(term: str, text: str) -> bool:
    """True when one surface form appears in the answer.

    Boundaries are enforced in two different ways, because the two kinds of
    term fail differently.

    A purely numeric term must not be read out of the middle of another number:
    required "8" is not satisfied by "48" or "0.87", and "0.25" is not satisfied
    by "10.25". But it may legitimately be followed by a letter or a sentence
    period, as in "3.24x speedup" or "is 8." An earlier version rejected both of
    those and scored correct answers as wrong.

    A short alphanumeric term such as "h2o", "nf4" or "3x" is bounded on
    letters and digits only, so trailing punctuation does not hide it.
    """
    haystacks = _haystacks(text)

    for candidate in _variants(term):
        if re.fullmatch(r"[\d.]+", candidate):
            # Not inside another number, either side.
            pattern = rf"(?<![\d.]){re.escape(candidate)}(?!\.?\d)"
        elif len(candidate) <= _SHORT_TERM_CHARS:
            pattern = rf"(?<![a-z0-9]){re.escape(candidate)}(?![a-z0-9])"
        else:
            if any(candidate in hay for hay in haystacks):
                return True
            continue
        if any(re.search(pattern, hay) for hay in haystacks):
            return True
    return False


def answer_matches(expected_answer: dict | None, text: str) -> tuple[bool, list[list[str]]]:
    """Check an answer against the required groups.

    Returns (matched, unmatched_groups). A task with no expected_answer returns
    (True, []) -- it is checked some other way, not by this function.
    """
    if not expected_answer:
        return True, []
    missing = [
        group
        for group in expected_answer["required"]
        if not any(term_present(term, text) for term in group)
    ]
    return not missing, missing


def validate_task(task: dict, *, seen_ids: set[str]) -> None:
    """Raise ValueError on anything that would make a task unscoreable."""
    missing = [field for field in REQUIRED_FIELDS if field not in task]
    if missing:
        raise ValueError(f"task {task.get('id', '<no id>')} is missing fields: {missing}")

    task_id = task["id"]
    if task_id in seen_ids:
        raise ValueError(f"duplicate task id: {task_id}")
    if task["category"] not in CATEGORIES:
        raise ValueError(f"task {task_id} has unknown category {task['category']!r}")
    if task["expected_route"] is not None and task["expected_route"] not in ROUTES:
        raise ValueError(f"task {task_id} has unknown route {task['expected_route']!r}")
    if not task["question"].strip():
        raise ValueError(f"task {task_id} has an empty question")

    if not (task["expected_route"] or task["expected_answer"] or task["expected_behavior"]):
        raise ValueError(f"task {task_id} carries no check at all")

    expected = task["expected_answer"]
    if expected is not None:
        groups = expected.get("required")
        if not groups or not all(isinstance(g, list) and g for g in groups):
            raise ValueError(f"task {task_id} has a malformed expected_answer")


def load_tasks(path: Path | str = TASKS_PATH) -> list[dict]:
    """Read and validate the whole task file."""
    tasks: list[dict] = []
    seen_ids: set[str] = set()
    with open(path) as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                task = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} is not valid JSON: {exc}") from exc
            validate_task(task, seen_ids=seen_ids)
            seen_ids.add(task["id"])
            tasks.append(task)
    return tasks
