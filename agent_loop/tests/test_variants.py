"""Checks on the wrapper variants.

The before and after comparison is only meaningful if the two runs differ in
exactly one setting and in nothing else. These tests pin that: baseline changes
nothing at all, the fix changes one flag, and neither touches anything in
AgentIQ.
"""

import pytest

from agent_loop.variants import (
    BASELINE,
    QUERY_EXPANSION,
    VARIANTS,
    apply_variant,
    variant_env,
)


def test_baseline_overrides_nothing() -> None:
    """The before run has to be AgentIQ exactly as it ships."""
    assert variant_env(BASELINE) == {}


def test_the_fix_changes_exactly_one_setting() -> None:
    """One targeted fix means one setting, not a bundle of them."""
    assert variant_env(QUERY_EXPANSION) == {"ENABLE_QUERY_REWRITING": "true"}


def test_the_two_variants_differ_in_one_key_only() -> None:
    before = variant_env(BASELINE)
    after = variant_env(QUERY_EXPANSION)
    changed = set(before) ^ set(after)
    assert len(changed) == 1
    assert changed == {"ENABLE_QUERY_REWRITING"}


def test_an_unknown_variant_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown variant"):
        variant_env("make_it_better")


def test_applying_a_variant_sets_the_environment() -> None:
    environ: dict[str, str] = {}
    applied = apply_variant(QUERY_EXPANSION, environ)
    assert environ["ENABLE_QUERY_REWRITING"] == "true"
    assert applied == {"ENABLE_QUERY_REWRITING": "true"}


def test_applying_baseline_leaves_the_environment_alone() -> None:
    environ = {"SOMETHING_ELSE": "1"}
    apply_variant(BASELINE, environ)
    assert environ == {"SOMETHING_ELSE": "1"}


def test_variant_env_returns_a_copy_not_the_shared_table() -> None:
    """A caller mutating the returned dict must not rewrite the variant."""
    env = variant_env(QUERY_EXPANSION)
    env["ENABLE_QUERY_REWRITING"] = "false"
    assert variant_env(QUERY_EXPANSION)["ENABLE_QUERY_REWRITING"] == "true"


def test_no_variant_touches_a_model_or_a_prompt() -> None:
    """The fix is a retrieval setting. If a variant ever starts changing the
    model, the before and after comparison stops being about retrieval."""
    forbidden = ("MODEL", "TEMPERATURE", "MAX_TOKENS", "PROMPT")
    for name, env in VARIANTS.items():
        for key in env:
            assert not any(word in key.upper() for word in forbidden), (
                f"variant {name} changes {key}, which is not a retrieval setting"
            )


def test_every_variant_is_env_only() -> None:
    """Variants configure AgentIQ from outside. Anything else would mean
    editing the agent, which this exercise does not do."""
    for name, env in VARIANTS.items():
        assert isinstance(env, dict), name
        for key, value in env.items():
            assert key.isupper(), f"{name}: {key} is not an environment variable name"
            assert isinstance(value, str), f"{name}: {key} must be a string"
