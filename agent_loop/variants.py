"""Wrapper level configurations the agent is run under.

A variant is a set of environment values applied before AgentIQ's config
singleton is built. Nothing here edits AgentIQ. Every variant is a
configuration this wrapper chooses, which is why the fix lives in this file
rather than in `agent/nodes.py`.

## Why query_expansion is the fix

The largest development failure cluster was `retrieval_miss`: 4 of 9 failures,
all on the retrieval route, all cases where the agent routed correctly, looked
in the corpus, and reported that its context did not contain the answer. The
fact was in the corpus every time. Adding `ignored_retrieved_evidence`, 6 of
the 9 failures sit on the retrieval path.

`agent/nodes.py:retriever_node` asks FAISS for `top_k=5` against the user's
question exactly as written, then keeps the best 3 chunks by score. One
phrasing, one shot. When the question words and the passage words diverge, the
right chunk never enters the candidate pool, and no amount of generation can
recover it.

AgentIQ already contains the machinery for a second attempt, behind a flag that
is off by default. With `ENABLE_QUERY_REWRITING=true`, `retriever_node` asks
the model for two paraphrases, runs FAISS for all three phrasings, merges the
results deduplicated by content, and keeps the best 3 by score. The candidate
pool grows from 5 chunks to as many as 15, so a chunk that the original wording
missed can still surface.

That makes this a retrieval setting change, one of the fix shapes the brief
allows, applied from outside the agent. It is one change: a single flag.

What it costs: one extra LLM call per retrieval run, for the paraphrases.

Why it might not work: the merged pool is still cut to the top 3 by score. If
the original phrasing's chunks already score highest, the new candidates never
make the cut and nothing changes. It is also possible for a paraphrase to
displace a chunk that was previously making it through, which would make some
answers worse. Both outcomes are reportable results, not reasons to try
something else afterwards.
"""

BASELINE = "baseline"
QUERY_EXPANSION = "query_expansion"
SUBQUESTION_GUARD = "subquestion_guard"

VARIANTS: dict[str, dict[str, str]] = {
    # AgentIQ's own defaults, untouched.
    BASELINE: {},
    # Candidate rejected at development validation: inert, see the module
    # docstring. Kept so the rejection is reproducible.
    QUERY_EXPANSION: {"ENABLE_QUERY_REWRITING": "true"},
    # The fix. It is wrapper logic, not a setting, so it overrides no
    # environment value: AgentIQ runs on its own defaults underneath.
    SUBQUESTION_GUARD: {},
}

# Variants whose behaviour lives in this wrapper rather than in a setting.
GUARDED_VARIANTS = frozenset({SUBQUESTION_GUARD})


def uses_guard(name: str) -> bool:
    """Whether this variant runs the sub question guard."""
    return name in GUARDED_VARIANTS


def variant_env(name: str) -> dict[str, str]:
    """The environment overrides a variant applies."""
    if name not in VARIANTS:
        raise ValueError(f"unknown variant {name!r}; known: {sorted(VARIANTS)}")
    return dict(VARIANTS[name])


def apply_variant(name: str, environ: dict | None = None) -> dict[str, str]:
    """Apply a variant's settings to the environment.

    Must run before anything imports AgentIQ's `config`, which reads these
    values once when its settings singleton is built. Returns what was applied,
    so a run can record the configuration it actually used rather than the one
    it intended.
    """
    import os

    target = os.environ if environ is None else environ
    applied = variant_env(name)
    for key, value in applied.items():
        target[key] = value
    return applied
