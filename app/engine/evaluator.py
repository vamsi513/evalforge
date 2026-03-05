from statistics import mean
from typing import Optional

from app.engine.evaluator_registry import ScoreContext, build_default_registry
from app.models.eval_run import (
    EvalCaseResult,
    EvalRunCreate,
    PairwiseCaseResult,
    PairwiseEvalCreate,
    PairwiseEvalResponse,
    PairwiseSample,
    RubricCriterion,
)


class EvalRunner:
    def __init__(self) -> None:
        self.registry = build_default_registry()

    def run(self, payload: EvalRunCreate) -> tuple[list[EvalCaseResult], float]:
        results: list[EvalCaseResult] = []
        for item in payload.samples:
            results.append(self._score_sample(item))
        avg_score = mean(result.score for result in results) if results else 0.0
        return results, avg_score

    def compare(self, payload: PairwiseEvalCreate) -> PairwiseEvalResponse:
        results: list[PairwiseCaseResult] = []
        wins_a = 0
        wins_b = 0
        ties = 0

        for item in payload.samples:
            result_a = self._score_candidate(
                prompt=item.prompt,
                expected_keyword=item.expected_keyword,
                candidate_output=item.candidate_a,
                scenario="general",
                slice_name="default",
                severity="medium",
                required_json_fields=[],
                reference_answer=item.reference_answer,
                rubric=item.rubric,
            )
            result_b = self._score_candidate(
                prompt=item.prompt,
                expected_keyword=item.expected_keyword,
                candidate_output=item.candidate_b,
                scenario="general",
                slice_name="default",
                severity="medium",
                required_json_fields=[],
                reference_answer=item.reference_answer,
                rubric=item.rubric,
            )

            if result_a.score > result_b.score:
                winner = "A"
                wins_a += 1
                rationale = "Candidate A satisfied more rubric coverage."
            elif result_b.score > result_a.score:
                winner = "B"
                wins_b += 1
                rationale = "Candidate B satisfied more rubric coverage."
            else:
                winner = "tie"
                ties += 1
                rationale = "Both candidates received the same heuristic score."

            results.append(
                PairwiseCaseResult(
                    prompt=item.prompt,
                    score_a=result_a.score,
                    score_b=result_b.score,
                    winner=winner,
                    rationale=rationale,
                )
            )

        total = len(payload.samples)
        return PairwiseEvalResponse(
            dataset_name=payload.dataset_name,
            prompt_version_a=payload.prompt_version_a,
            prompt_version_b=payload.prompt_version_b,
            model_name=payload.model_name,
            win_rate_a=round(wins_a / total, 4) if total else 0.0,
            win_rate_b=round(wins_b / total, 4) if total else 0.0,
            ties=ties,
            results=results,
        )

    def _score_sample(self, item) -> EvalCaseResult:
        return self._score_candidate(
            prompt=item.prompt,
            expected_keyword=item.expected_keyword,
            candidate_output=item.candidate_output,
            scenario=item.scenario,
            slice_name=item.slice_name,
            severity=item.severity,
            required_json_fields=item.required_json_fields,
            reference_answer=item.reference_answer,
            rubric=item.rubric,
        )

    def _score_candidate(
        self,
        *,
        prompt: str,
        expected_keyword: str,
        candidate_output: str,
        scenario: str,
        slice_name: str,
        severity: str,
        required_json_fields: list[str],
        reference_answer: Optional[str],
        rubric: list[RubricCriterion],
    ) -> EvalCaseResult:
        prompt_tokens = max(1, len(prompt.split()))
        response_tokens = max(1, len(candidate_output.split()))
        score_context = ScoreContext(
            prompt=prompt,
            expected_keyword=expected_keyword,
            candidate_output=candidate_output,
            required_json_fields=required_json_fields,
            reference_answer=reference_answer,
            rubric=rubric,
        )
        score_result = self.registry.evaluate(score_context)
        score = round(min(1.0, score_result.score), 4)
        passed = score >= 0.65

        if passed:
            feedback = " ".join(score_result.feedback_messages) or "Output met the heuristic quality threshold."
        else:
            feedback = " ".join(score_result.feedback_messages) or "Output missed key rubric or reference signals."

        return EvalCaseResult(
            prompt=prompt,
            expected_keyword=expected_keyword,
            candidate_output=candidate_output,
            scenario=scenario,
            slice_name=slice_name,
            severity=severity,
            required_json_fields=required_json_fields,
            reference_answer=reference_answer,
            rubric=rubric,
            score=score,
            latency_ms=prompt_tokens * 8 + response_tokens * 3,
            cost_usd=round((prompt_tokens + response_tokens) * 0.00001, 6),
            passed=passed,
            matched_terms=score_result.matched_terms,
            missing_terms=score_result.missing_terms,
            unsupported_terms=score_result.unsupported_terms,
            criterion_scores=score_result.criterion_scores,
            structured_output_valid=score_result.structured_output_valid,
            structured_output_error=score_result.structured_output_error,
            groundedness_score=score_result.groundedness_score,
            groundedness_feedback=score_result.groundedness_feedback,
            feedback=feedback,
        )


eval_runner = EvalRunner()
