from statistics import mean
from typing import Optional

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
                reference_answer=item.reference_answer,
                rubric=item.rubric,
            )
            result_b = self._score_candidate(
                prompt=item.prompt,
                expected_keyword=item.expected_keyword,
                candidate_output=item.candidate_b,
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
            reference_answer=item.reference_answer,
            rubric=item.rubric,
        )

    def _score_candidate(
        self,
        *,
        prompt: str,
        expected_keyword: str,
        candidate_output: str,
        reference_answer: Optional[str],
        rubric: list[RubricCriterion],
    ) -> EvalCaseResult:
        prompt_tokens = max(1, len(prompt.split()))
        response_tokens = max(1, len(candidate_output.split()))
        normalized_output = candidate_output.lower()
        matched_terms: list[str] = []
        missing_terms: list[str] = []
        criterion_scores: dict[str, float] = {}

        keyword_hit = expected_keyword.lower() in normalized_output
        base_score = 0.4 if keyword_hit else 0.0
        if keyword_hit:
            matched_terms.append(expected_keyword)
        else:
            missing_terms.append(expected_keyword)

        reference_overlap = 0.0
        if reference_answer:
            reference_terms = {term.lower() for term in reference_answer.split() if len(term) > 4}
            overlap_hits = [term for term in reference_terms if term in normalized_output]
            reference_overlap = min(0.3, len(overlap_hits) * 0.05)
            matched_terms.extend(term for term in overlap_hits if term not in matched_terms)

        rubric_score = 0.0
        rubric_weights = sum(criterion.weight for criterion in rubric) or 1.0
        for criterion in rubric:
            required = [term.lower() for term in criterion.required_terms]
            hits = [term for term in required if term in normalized_output]
            ratio = len(hits) / len(required) if required else 1.0
            weighted_score = ratio * criterion.weight
            criterion_scores[criterion.name] = round(weighted_score, 4)
            rubric_score += weighted_score
            matched_terms.extend(term for term in hits if term not in matched_terms)
            missing_terms.extend(term for term in required if term not in hits and term not in missing_terms)

        normalized_rubric_score = 0.3 * (rubric_score / rubric_weights) if rubric else 0.0
        score = round(min(1.0, base_score + reference_overlap + normalized_rubric_score), 4)
        passed = score >= 0.65

        if passed:
            feedback = "Output met the heuristic quality threshold."
        else:
            feedback = "Output missed key rubric or reference signals."

        return EvalCaseResult(
            prompt=prompt,
            expected_keyword=expected_keyword,
            candidate_output=candidate_output,
            reference_answer=reference_answer,
            rubric=rubric,
            score=score,
            latency_ms=prompt_tokens * 8 + response_tokens * 3,
            cost_usd=round((prompt_tokens + response_tokens) * 0.00001, 6),
            passed=passed,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
            criterion_scores=criterion_scores,
            feedback=feedback,
        )


eval_runner = EvalRunner()
