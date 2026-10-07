"""Regression tests for the silent judge fallback.

The bug these cover: the structured output schema was sent to OpenAI with
`strict: true`, but `criterion_scores` is an open-ended `{name: number}` map,
which is not representable in OpenAI's strict-mode subset. Every real call
returned 400, the `except` block in `_evaluate_openai` swallowed it, and the
deterministic mock judge was substituted without any signal. Results that
looked like model grades were mock grades.

Two things were wrong and both are asserted here:

1. The fallback was silent. It must now be loud: a WARNING naming the
   provider, model and reason, and `used_fallback` set on every result.
2. `latency_ms` and `cost_usd` were taken from the judge model's own JSON
   response, which the prompt invited it to estimate. They must now come from
   wall-clock timing and from the token usage the provider reports.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.engine import judge as judge_module
from app.engine.judge import JudgeClient
from app.models.eval_run import EvalSample

SAMPLE = EvalSample(
    prompt="What is the capital of France?",
    expected_keyword="Paris",
    candidate_output="The capital of France is Paris.",
)

# What the judge model is asked to return. The latency and cost values here are
# deliberately absurd: if either reaches the result, the code trusted the model
# instead of measuring.
MODEL_REPORTED = {
    "score": 0.9,
    "passed": True,
    "criterion_scores": {"accuracy": 0.9},
    "feedback": "Correct.",
    "judge_reasoning": "Names Paris.",
    "matched_terms": ["paris"],
    "missing_terms": [],
    "latency_ms": 999_999,
    "cost_usd": 12.34,
}


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            # What httpx raises for a 400, and what the judge catches.
            raise httpx.HTTPStatusError(
                f"{self.status_code} Bad Request",
                request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Stands in for httpx.Client, which the judge builds internally."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict] = []

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "json": json})
        return self._response


@pytest.fixture
def openai_judge(monkeypatch):
    """Force the OpenAI judge path with a key present."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "judge_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test000key000for000fallback000abcd")
    monkeypatch.setattr(settings, "judge_model", "gpt-4o-mini")
    return settings


def _install(monkeypatch, response: _FakeResponse) -> _FakeClient:
    fake = _FakeClient(response)
    monkeypatch.setattr(judge_module.httpx, "Client", fake)
    return fake


def _evaluate() -> object:
    return JudgeClient().evaluate(
        dataset_name="fallback-test",
        prompt_version="v1",
        model_name="gpt-4o-mini",
        samples=[SAMPLE],
    )


class TestSchemaShapeThatCausedTheBug:
    def test_criterion_scores_is_an_open_ended_map(self):
        """This is the construct strict mode cannot express."""
        schema = JudgeClient()._response_schema()
        criterion = schema["properties"]["criterion_scores"]
        assert criterion["type"] == "object"
        assert criterion["additionalProperties"] == {"type": "number"}

    def test_the_request_does_not_ask_for_strict_mode(self, openai_judge, monkeypatch):
        """Regression guard: strict:true here is what produced the 400."""
        fake = _install(
            monkeypatch,
            _FakeResponse(
                200,
                {
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                    "choices": [{"message": {"content": json.dumps(MODEL_REPORTED)}}],
                },
            ),
        )
        _evaluate()
        sent = fake.calls[0]["json"]
        assert sent["response_format"]["json_schema"]["strict"] is False


class TestFallbackIsNoLongerSilent:
    def test_a_400_marks_used_fallback_on_every_result(self, openai_judge, monkeypatch):
        _install(monkeypatch, _FakeResponse(400, {}))
        response = _evaluate()
        assert response.results
        assert all(result.used_fallback is True for result in response.results)

    def test_a_400_logs_a_warning_naming_provider_model_and_reason(
        self, openai_judge, monkeypatch, caplog
    ):
        _install(monkeypatch, _FakeResponse(400, {}))
        with caplog.at_level(logging.WARNING, logger=judge_module.logger.name):
            _evaluate()

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings, "the fallback must not be silent"
        message = " ".join(r.getMessage() for r in warnings)
        assert "Judge fallback activated" in message
        assert "openai" in message
        assert "gpt-4o-mini" in message
        # The reason carries the underlying failure, not just a generic note.
        assert "400" in message

    def test_the_result_feedback_explains_the_fallback(self, openai_judge, monkeypatch):
        _install(monkeypatch, _FakeResponse(400, {}))
        response = _evaluate()
        assert "fallback" in response.results[0].feedback.lower()

    def test_a_successful_call_does_not_mark_a_fallback(self, openai_judge, monkeypatch):
        _install(
            monkeypatch,
            _FakeResponse(
                200,
                {
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                    "choices": [{"message": {"content": json.dumps(MODEL_REPORTED)}}],
                },
            ),
        )
        response = _evaluate()
        assert all(result.used_fallback is False for result in response.results)
        assert response.judge_provider == "openai"

    def test_a_missing_key_also_marks_a_fallback(self, openai_judge, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "openai_api_key", "")
        response = _evaluate()
        assert all(result.used_fallback is True for result in response.results)


class TestLatencyAndCostAreMeasuredNotReported:
    def test_latency_does_not_come_from_the_response_body(self, openai_judge, monkeypatch):
        _install(
            monkeypatch,
            _FakeResponse(
                200,
                {
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                    "choices": [{"message": {"content": json.dumps(MODEL_REPORTED)}}],
                },
            ),
        )
        result = _evaluate().results[0]
        # The model claimed 999999 ms. A stubbed call takes a few ms at most.
        assert result.latency_ms != MODEL_REPORTED["latency_ms"]
        assert 0 < result.latency_ms < 5_000

    def test_cost_is_computed_from_reported_token_usage(self, openai_judge, monkeypatch):
        _install(
            monkeypatch,
            _FakeResponse(
                200,
                {
                    "model": "gpt-4o-mini",
                    "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
                    "choices": [{"message": {"content": json.dumps(MODEL_REPORTED)}}],
                },
            ),
        )
        result = _evaluate().results[0]
        # gpt-4o-mini list pricing: 0.15 per 1M prompt, 0.60 per 1M completion.
        assert result.cost_usd == pytest.approx(0.75, rel=1e-6)
        assert result.cost_usd != MODEL_REPORTED["cost_usd"]

    def test_cost_is_zero_when_the_provider_reports_no_usage(
        self, openai_judge, monkeypatch
    ):
        """Without usage there is nothing to price, so no cost is invented."""
        body = {
            "model": "gpt-4o-mini",
            "choices": [{"message": {"content": json.dumps({**MODEL_REPORTED, "cost_usd": 0.0})}}],
        }
        _install(monkeypatch, _FakeResponse(200, body))
        result = _evaluate().results[0]
        assert result.cost_usd == 0.0

    def test_an_unknown_model_is_not_priced_from_a_guess(self, openai_judge, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "judge_model", "some-unreleased-model")
        body = {
            "model": "some-unreleased-model",
            "usage": {"prompt_tokens": 1_000, "completion_tokens": 1_000},
            "choices": [{"message": {"content": json.dumps({**MODEL_REPORTED, "cost_usd": 0.0})}}],
        }
        _install(monkeypatch, _FakeResponse(200, body))
        result = _evaluate().results[0]
        # No pricing entry, so nothing is charged rather than a number guessed.
        assert result.cost_usd == 0.0
