import json
import logging
import re
import time
from statistics import mean
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.models.eval_run import EvalSample, JudgeCaseResult, JudgeEvalResponse

# Published list pricing, USD per token. Keyed by model name; used to
# compute real cost_usd from actual token usage rather than trusting the
# judge model's self-reported estimate.
_TOKEN_PRICING_USD: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000},
    "gpt-4o": {"prompt": 2.50 / 1_000_000, "completion": 10.00 / 1_000_000},
    # https://www.anthropic.com/pricing#api
    "claude-haiku-4-5": {"prompt": 1.00 / 1_000_000, "completion": 5.00 / 1_000_000},
    # https://mistral.ai/pricing#api-pricing
    "mistral-small-latest": {"prompt": 0.10 / 1_000_000, "completion": 0.30 / 1_000_000},
}


def _ensure_v1_path(base_url: str) -> str:
    """Normalize a provider base URL to always include the /v1 API path.

    Ambient environment variables (e.g. ANTHROPIC_BASE_URL set globally by
    unrelated tools on a dev machine) can override this app's own .env and
    strip the /v1 suffix, silently breaking every request. Env vars always
    take precedence over .env file values for pydantic-settings, so this
    can't be fixed by config alone -- normalize it defensively instead.
    """
    trimmed = base_url.rstrip("/")
    return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"


class JudgeClient:
    def evaluate(
        self, *, dataset_name: str, prompt_version: str, model_name: str, samples: list[EvalSample]
    ) -> JudgeEvalResponse:
        provider = settings.judge_provider.lower()
        if provider == "openai":
            return self._evaluate_openai(
                dataset_name=dataset_name,
                prompt_version=prompt_version,
                model_name=model_name,
                samples=samples,
            )
        if provider == "anthropic":
            return self._evaluate_anthropic(
                dataset_name=dataset_name,
                prompt_version=prompt_version,
                model_name=model_name,
                samples=samples,
            )
        if provider == "mistral":
            return self._evaluate_mistral(
                dataset_name=dataset_name,
                prompt_version=prompt_version,
                model_name=model_name,
                samples=samples,
            )
        return self._evaluate_mock(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            samples=samples,
        )

    def _evaluate_mock(
        self, *, dataset_name: str, prompt_version: str, model_name: str, samples: list[EvalSample]
    ) -> JudgeEvalResponse:
        results: list[JudgeCaseResult] = []
        for sample in samples:
            results.append(self._score_with_mock(sample))

        return JudgeEvalResponse(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            judge_provider="mock",
            judge_model="heuristic-judge-v1",
            average_score=round(mean(result.score for result in results), 4) if results else 0.0,
            results=results,
        )

    def _evaluate_openai(
        self, *, dataset_name: str, prompt_version: str, model_name: str, samples: list[EvalSample]
    ) -> JudgeEvalResponse:
        mock_response = self._evaluate_mock(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            samples=samples,
        )

        if not settings.openai_api_key:
            return self._mark_fallback(
                response=mock_response,
                provider="openai",
                model=settings.judge_model,
                feedback="OpenAI key missing. Used mock judge fallback.",
            )

        try:
            results = [self._score_with_openai(sample) for sample in samples]
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return self._mark_fallback(
                response=mock_response,
                provider="openai",
                model=settings.judge_model,
                feedback=f"OpenAI judge failed ({exc}). Used mock judge fallback.",
            )

        return JudgeEvalResponse(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            judge_provider="openai",
            judge_model=settings.judge_model,
            average_score=round(mean(result.score for result in results), 4) if results else 0.0,
            results=results,
        )

    def _score_with_openai(self, sample: EvalSample) -> JudgeCaseResult:
        payload = {
            "model": settings.judge_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(sample)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "evalforge_judge_result",
                    "schema": self._response_schema(),
                    # strict:true rejects criterion_scores (an open-ended
                    # {name: score} map — additionalProperties as a schema
                    # isn't representable in OpenAI's strict subset).
                    "strict": False,
                },
            },
        }

        start = time.perf_counter()
        with httpx.Client(base_url=_ensure_v1_path(settings.openai_base_url), timeout=20.0) as client:
            response = client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        measured_latency_ms = (time.perf_counter() - start) * 1000
        measured_cost_usd = self._measured_cost_usd(body)

        content = self._extract_message_content(body)
        parsed = json.loads(content)
        return self._build_judge_result(
            sample,
            parsed,
            provider="openai",
            model=settings.judge_model,
            measured_latency_ms=measured_latency_ms,
            measured_cost_usd=measured_cost_usd,
        )

    def _evaluate_anthropic(
        self, *, dataset_name: str, prompt_version: str, model_name: str, samples: list[EvalSample]
    ) -> JudgeEvalResponse:
        mock_response = self._evaluate_mock(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            samples=samples,
        )

        if not settings.anthropic_api_key:
            return self._mark_fallback(
                response=mock_response,
                provider="anthropic",
                model=settings.judge_model_anthropic,
                feedback="Anthropic key missing. Used mock judge fallback.",
            )

        try:
            results = [self._score_with_anthropic(sample) for sample in samples]
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return self._mark_fallback(
                response=mock_response,
                provider="anthropic",
                model=settings.judge_model_anthropic,
                feedback=f"Anthropic judge failed ({exc}). Used mock judge fallback.",
            )

        return JudgeEvalResponse(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            judge_provider="anthropic",
            judge_model=settings.judge_model_anthropic,
            average_score=round(mean(result.score for result in results), 4) if results else 0.0,
            results=results,
        )

    def _score_with_anthropic(self, sample: EvalSample) -> JudgeCaseResult:
        # Claude has no OpenAI-style response_format:json_schema. Forcing a
        # tool call is Anthropic's documented way to get reliable structured
        # output: the model must call this tool, whose input_schema is our
        # judge schema, so `content[0].input` is already a parsed dict.
        payload = {
            "model": settings.judge_model_anthropic,
            "max_tokens": 1024,
            "system": self._system_prompt(),
            "messages": [{"role": "user", "content": self._user_prompt(sample)}],
            "tools": [
                {
                    "name": "evalforge_judge_result",
                    "description": "Return the structured judge scoring result.",
                    "input_schema": self._response_schema(),
                }
            ],
            "tool_choice": {"type": "tool", "name": "evalforge_judge_result"},
        }

        start = time.perf_counter()
        with httpx.Client(base_url=_ensure_v1_path(settings.anthropic_base_url), timeout=20.0) as client:
            response = client.post(
                "/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        measured_latency_ms = (time.perf_counter() - start) * 1000
        measured_cost_usd = self._measured_cost_usd_anthropic(body)

        parsed = self._extract_anthropic_tool_input(body)
        return self._build_judge_result(
            sample,
            parsed,
            provider="anthropic",
            model=settings.judge_model_anthropic,
            measured_latency_ms=measured_latency_ms,
            measured_cost_usd=measured_cost_usd,
        )

    @staticmethod
    def _extract_anthropic_tool_input(body: dict[str, Any]) -> dict[str, Any]:
        for block in body.get("content", []):
            if block.get("type") == "tool_use":
                return block.get("input", {})
        raise ValueError("No tool_use block returned by Anthropic")

    @staticmethod
    def _measured_cost_usd_anthropic(body: dict[str, Any]) -> Optional[float]:
        usage = body.get("usage")
        model = body.get("model", "")
        if not usage:
            return None
        pricing = next((rates for name, rates in _TOKEN_PRICING_USD.items() if model.startswith(name)), None)
        if pricing is None:
            return None
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        return prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]

    def _evaluate_mistral(
        self, *, dataset_name: str, prompt_version: str, model_name: str, samples: list[EvalSample]
    ) -> JudgeEvalResponse:
        mock_response = self._evaluate_mock(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            samples=samples,
        )

        if not settings.mistral_api_key:
            return self._mark_fallback(
                response=mock_response,
                provider="mistral",
                model=settings.judge_model_mistral,
                feedback="Mistral key missing. Used mock judge fallback.",
            )

        try:
            results = [self._score_with_mistral(sample) for sample in samples]
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return self._mark_fallback(
                response=mock_response,
                provider="mistral",
                model=settings.judge_model_mistral,
                feedback=f"Mistral judge failed ({exc}). Used mock judge fallback.",
            )

        return JudgeEvalResponse(
            dataset_name=dataset_name,
            prompt_version=prompt_version,
            model_name=model_name,
            judge_provider="mistral",
            judge_model=settings.judge_model_mistral,
            average_score=round(mean(result.score for result in results), 4) if results else 0.0,
            results=results,
        )

    def _score_with_mistral(self, sample: EvalSample) -> JudgeCaseResult:
        # Mistral's chat/completions endpoint is OpenAI-shaped: same
        # choices[0].message.content envelope, JSON mode via response_format.
        payload = {
            "model": settings.judge_model_mistral,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(sample)},
            ],
            "response_format": {"type": "json_object"},
        }

        start = time.perf_counter()
        with httpx.Client(base_url=_ensure_v1_path(settings.mistral_base_url), timeout=20.0) as client:
            response = client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.mistral_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        measured_latency_ms = (time.perf_counter() - start) * 1000
        measured_cost_usd = self._measured_cost_usd(body)

        content = self._extract_message_content(body)
        parsed = json.loads(content)
        return self._build_judge_result(
            sample,
            parsed,
            provider="mistral",
            model=settings.judge_model_mistral,
            measured_latency_ms=measured_latency_ms,
            measured_cost_usd=measured_cost_usd,
        )

    @staticmethod
    def _measured_cost_usd(body: dict[str, Any]) -> Optional[float]:
        usage = body.get("usage")
        model = body.get("model", "")
        if not usage:
            return None
        pricing = next((rates for name, rates in _TOKEN_PRICING_USD.items() if model.startswith(name)), None)
        if pricing is None:
            return None
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        return prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]

    def _build_judge_result(
        self,
        sample: EvalSample,
        parsed: dict[str, Any],
        *,
        provider: str,
        model: str,
        measured_latency_ms: float,
        measured_cost_usd: Optional[float],
    ) -> JudgeCaseResult:
        criterion_scores_raw = parsed.get("criterion_scores", {})
        criterion_scores = {
            str(name): round(float(score), 4) for name, score in criterion_scores_raw.items()
        }
        matched_terms = [str(term).lower() for term in parsed.get("matched_terms", [])]
        missing_terms = [str(term).lower() for term in parsed.get("missing_terms", [])]
        score = round(float(parsed["score"]), 4)
        groundedness_score, unsupported_terms, groundedness_feedback = self._groundedness_snapshot(sample)
        criterion_scores.setdefault("groundedness", groundedness_score)

        return JudgeCaseResult(
            prompt=sample.prompt,
            expected_keyword=sample.expected_keyword,
            candidate_output=sample.candidate_output,
            reference_answer=sample.reference_answer,
            rubric=sample.rubric,
            score=score,
            latency_ms=max(1, round(measured_latency_ms)),
            cost_usd=round(measured_cost_usd, 6) if measured_cost_usd is not None else round(float(parsed.get("cost_usd", 0.0)), 6),
            passed=bool(parsed.get("passed", score >= 0.7)),
            matched_terms=matched_terms,
            missing_terms=missing_terms,
            unsupported_terms=unsupported_terms,
            criterion_scores=criterion_scores,
            groundedness_score=groundedness_score,
            groundedness_feedback=groundedness_feedback,
            feedback=str(parsed.get("feedback", "Structured LLM judge completed scoring.")),
            judge_provider=provider,
            judge_model=model,
            judge_score=score,
            judge_reasoning=str(parsed["judge_reasoning"]),
            used_fallback=False,
        )

    @staticmethod
    def _extract_message_content(body: dict[str, Any]) -> str:
        choices = body.get("choices", [])
        if not choices:
            raise ValueError("No completion choices returned")
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
            ]
            joined = "".join(text_parts).strip()
            if joined:
                return joined
        raise ValueError("No structured message content returned")

    @staticmethod
    def _mark_fallback(
        *, response: JudgeEvalResponse, provider: str, model: str, feedback: str
    ) -> JudgeEvalResponse:
        logger.warning(
            "Judge fallback activated: provider=%s model=%s reason=%s samples=%d",
            provider, model, feedback, len(response.results),
        )
        response.judge_provider = provider
        response.judge_model = model
        for result in response.results:
            result.judge_provider = provider
            result.judge_model = model
            result.used_fallback = True
            result.feedback = feedback
        return response

    @staticmethod
    def _score_with_mock(sample: EvalSample) -> JudgeCaseResult:
        output = sample.candidate_output.lower()
        keyword_hit = sample.expected_keyword.lower() in output
        rubric_hits = 0
        total_terms = 0
        matched_terms: list[str] = []
        missing_terms: list[str] = []
        criterion_scores: dict[str, float] = {}

        for criterion in sample.rubric:
            required_terms = [term.lower() for term in criterion.required_terms]
            total_terms += len(required_terms)
            hits = [term for term in required_terms if term in output]
            rubric_hits += len(hits)
            matched_terms.extend(term for term in hits if term not in matched_terms)
            missing_terms.extend(term for term in required_terms if term not in hits)
            criterion_scores[criterion.name] = round(
                (len(hits) / len(required_terms) if required_terms else 1.0) * criterion.weight, 4
            )

        score = 0.45 if keyword_hit else 0.0
        if sample.reference_answer:
            reference_terms = [term.lower() for term in sample.reference_answer.split() if len(term) > 4]
            overlap = len([term for term in reference_terms if term in output])
            score += min(0.25, overlap * 0.05)
        if total_terms:
            score += 0.3 * (rubric_hits / total_terms)
        score = round(min(score, 1.0), 4)
        if keyword_hit and sample.expected_keyword.lower() not in matched_terms:
            matched_terms.append(sample.expected_keyword.lower())
        if not keyword_hit:
            missing_terms.append(sample.expected_keyword.lower())
        groundedness_score, unsupported_terms, groundedness_feedback = JudgeClient._groundedness_snapshot(sample)
        criterion_scores.setdefault("groundedness", groundedness_score)

        return JudgeCaseResult(
            prompt=sample.prompt,
            expected_keyword=sample.expected_keyword,
            candidate_output=sample.candidate_output,
            reference_answer=sample.reference_answer,
            rubric=sample.rubric,
            score=score,
            latency_ms=max(10, len(sample.prompt.split()) * 9),
            cost_usd=round((len(sample.prompt.split()) + len(sample.candidate_output.split())) * 0.00002, 6),
            passed=score >= 0.7,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
            unsupported_terms=unsupported_terms,
            criterion_scores=criterion_scores,
            groundedness_score=groundedness_score,
            groundedness_feedback=groundedness_feedback,
            feedback="Mock judge completed rubric-based scoring.",
            judge_provider="mock",
            judge_model="heuristic-judge-v1",
            judge_score=score,
            judge_reasoning="Score reflects expected keyword coverage, reference overlap, and rubric term matches.",
            used_fallback=False,
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are EvalForge Judge, a strict LLM evaluation grader. "
            "Score the candidate output against the expected keyword, reference answer, and rubric. "
            "Return only JSON matching the provided schema."
        )

    @staticmethod
    def _user_prompt(sample: EvalSample) -> str:
        rubric_lines = []
        for criterion in sample.rubric:
            rubric_lines.append(
                f"- {criterion.name}: {criterion.description}. "
                f"weight={criterion.weight}. required_terms={criterion.required_terms}"
            )

        return (
            f"Prompt:\n{sample.prompt}\n\n"
            f"Expected keyword:\n{sample.expected_keyword}\n\n"
            f"Candidate output:\n{sample.candidate_output}\n\n"
            f"Reference answer:\n{sample.reference_answer or 'None provided'}\n\n"
            f"Rubric:\n{chr(10).join(rubric_lines) if rubric_lines else '- No explicit rubric provided'}\n\n"
            "Instructions:\n"
            "1. Produce a score between 0.0 and 1.0.\n"
            "2. Mark passed=true only if the answer satisfies the prompt and rubric at production quality.\n"
            "3. matched_terms should contain rubric or reference terms that appear in the answer.\n"
            "4. missing_terms should contain important required terms that do not appear.\n"
            "5. criterion_scores should use rubric criterion names as keys and normalized per-criterion scores as values.\n"
            "6. feedback should be brief and actionable.\n"
            "7. judge_reasoning should explain the score briefly.\n"
            "8. latency_ms and cost_usd may be estimated.\n"
        )

    @staticmethod
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0, "maximum": 1},
                "passed": {"type": "boolean"},
                "matched_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "missing_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "criterion_scores": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                "feedback": {"type": "string"},
                "judge_reasoning": {"type": "string"},
                "latency_ms": {"type": "integer", "minimum": 1},
                "cost_usd": {"type": "number", "minimum": 0},
            },
            "required": [
                "score",
                "passed",
                "matched_terms",
                "missing_terms",
                "criterion_scores",
                "feedback",
                "judge_reasoning",
                "latency_ms",
                "cost_usd",
            ],
            "additionalProperties": False,
        }

    @staticmethod
    def _groundedness_snapshot(sample: EvalSample) -> tuple[float, list[str], str]:
        if not sample.reference_answer:
            return 1.0, [], "No reference answer provided for groundedness checks."

        reference_terms = JudgeClient._extract_terms(sample.reference_answer)
        candidate_terms = JudgeClient._extract_terms(sample.candidate_output)
        if not candidate_terms:
            return 1.0, [], "Candidate output did not contain enough signal for groundedness checks."

        unsupported_terms = sorted(term for term in candidate_terms if term not in reference_terms)
        overlap_terms = [term for term in candidate_terms if term in reference_terms]
        groundedness_score = len(overlap_terms) / (len(candidate_terms) + (2 * len(unsupported_terms)))
        rounded_score = round(max(0.0, min(1.0, groundedness_score)), 4)
        if unsupported_terms:
            return (
                rounded_score,
                unsupported_terms,
                f"Unsupported terms detected: {', '.join(unsupported_terms[:5])}.",
            )
        return rounded_score, [], "All significant answer terms were grounded in the reference."

    @staticmethod
    def _extract_terms(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{4,}", text.lower())
            if token not in {"issue", "summary", "response", "result"}
        }


judge_client = JudgeClient()
