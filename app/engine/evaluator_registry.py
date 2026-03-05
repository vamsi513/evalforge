import json
import re
from dataclasses import dataclass, field
from typing import Optional

from app.models.eval_run import RubricCriterion


@dataclass
class ScoreContext:
    prompt: str
    expected_keyword: str
    candidate_output: str
    required_json_fields: list[str]
    reference_answer: Optional[str]
    rubric: list[RubricCriterion]


@dataclass
class ScoreAccumulator:
    score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    unsupported_terms: list[str] = field(default_factory=list)
    criterion_scores: dict[str, float] = field(default_factory=dict)
    feedback_messages: list[str] = field(default_factory=list)
    structured_output_valid: bool = False
    structured_output_error: str = ""
    groundedness_score: float = 1.0
    groundedness_feedback: str = ""

    def add_match(self, term: str) -> None:
        if term not in self.matched_terms:
            self.matched_terms.append(term)
        if term in self.missing_terms:
            self.missing_terms.remove(term)

    def add_missing(self, term: str) -> None:
        if term not in self.missing_terms and term not in self.matched_terms:
            self.missing_terms.append(term)


class BaseEvaluator:
    name = "base"
    kind = "heuristic"

    def evaluate(self, context: ScoreContext, accumulator: ScoreAccumulator) -> None:
        raise NotImplementedError


class KeywordEvaluator(BaseEvaluator):
    name = "keyword"
    kind = "keyword"

    def evaluate(self, context: ScoreContext, accumulator: ScoreAccumulator) -> None:
        keyword = context.expected_keyword.lower()
        if keyword in context.candidate_output.lower():
            accumulator.score += 0.4
            accumulator.add_match(context.expected_keyword)
            accumulator.feedback_messages.append("Matched expected keyword.")
        else:
            accumulator.add_missing(context.expected_keyword)
            accumulator.feedback_messages.append("Missed expected keyword.")


class ReferenceOverlapEvaluator(BaseEvaluator):
    name = "reference_overlap"
    kind = "reference_overlap"

    def evaluate(self, context: ScoreContext, accumulator: ScoreAccumulator) -> None:
        if not context.reference_answer:
            return
        reference_terms = {term.lower() for term in context.reference_answer.split() if len(term) > 4}
        overlap_hits = [term for term in reference_terms if term in context.candidate_output.lower()]
        accumulator.score += min(0.3, len(overlap_hits) * 0.05)
        for term in overlap_hits:
            accumulator.add_match(term)
        if overlap_hits:
            accumulator.feedback_messages.append("Reference overlap improved confidence.")


class RubricCoverageEvaluator(BaseEvaluator):
    name = "rubric"
    kind = "rubric"

    def evaluate(self, context: ScoreContext, accumulator: ScoreAccumulator) -> None:
        if not context.rubric:
            return
        total_weight = sum(criterion.weight for criterion in context.rubric) or 1.0
        weighted_score = 0.0
        normalized_output = context.candidate_output.lower()
        for criterion in context.rubric:
            required = [term.lower() for term in criterion.required_terms]
            hits = [term for term in required if term in normalized_output]
            ratio = len(hits) / len(required) if required else 1.0
            criterion_score = ratio * criterion.weight
            accumulator.criterion_scores[criterion.name] = round(criterion_score, 4)
            weighted_score += criterion_score
            for term in hits:
                accumulator.add_match(term)
            for term in required:
                if term not in hits:
                    accumulator.add_missing(term)
        accumulator.score += 0.3 * (weighted_score / total_weight)
        accumulator.feedback_messages.append("Applied rubric coverage scoring.")


class StructuredOutputEvaluator(BaseEvaluator):
    name = "structured_output"
    kind = "validator"

    def evaluate(self, context: ScoreContext, accumulator: ScoreAccumulator) -> None:
        output = context.candidate_output.strip()
        if not context.required_json_fields:
            if not output.startswith("{"):
                return
        elif not output.startswith("{"):
            accumulator.structured_output_valid = False
            accumulator.structured_output_error = "Output is not valid JSON."
            accumulator.feedback_messages.append("Structured output validation failed.")
            accumulator.criterion_scores["structured_output"] = 0.0
            accumulator.add_missing("structured_output")
            accumulator.score = max(0.0, accumulator.score - 0.1)
            return
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            accumulator.structured_output_valid = False
            accumulator.structured_output_error = "JSON parsing failed."
            accumulator.feedback_messages.append("Structured output parsing failed.")
            accumulator.criterion_scores["structured_output"] = 0.0
            accumulator.add_missing("structured_output")
            if context.required_json_fields:
                accumulator.score = max(0.0, accumulator.score - 0.1)
            return
        if not isinstance(parsed, dict):
            accumulator.structured_output_valid = False
            accumulator.structured_output_error = "Structured output must be a JSON object."
            accumulator.feedback_messages.append("Structured output must be a JSON object.")
            accumulator.criterion_scores["structured_output"] = 0.0
            if context.required_json_fields:
                accumulator.score = max(0.0, accumulator.score - 0.1)
            return

        missing_fields = [field for field in context.required_json_fields if field not in parsed]
        if missing_fields:
            accumulator.structured_output_valid = False
            accumulator.structured_output_error = f"Missing required JSON fields: {', '.join(missing_fields)}."
            accumulator.feedback_messages.append("Structured output schema validation failed.")
            accumulator.criterion_scores["structured_output"] = 0.0
            for field in missing_fields:
                accumulator.add_missing(field)
            accumulator.score = max(0.0, accumulator.score - 0.1)
            return

        accumulator.structured_output_valid = True
        accumulator.structured_output_error = ""
        accumulator.score += 0.05
        accumulator.criterion_scores["structured_output"] = 0.05
        accumulator.feedback_messages.append("Structured output parsed successfully.")
        for field in context.required_json_fields:
            accumulator.add_match(field)


class GroundednessEvaluator(BaseEvaluator):
    name = "groundedness"
    kind = "groundedness"

    def evaluate(self, context: ScoreContext, accumulator: ScoreAccumulator) -> None:
        if not context.reference_answer:
            accumulator.groundedness_score = 1.0
            accumulator.groundedness_feedback = "No reference answer provided for groundedness checks."
            return

        reference_terms = self._extract_terms(context.reference_answer)
        candidate_terms = self._extract_terms(context.candidate_output)

        if not candidate_terms:
            accumulator.groundedness_score = 1.0
            accumulator.groundedness_feedback = "Candidate output did not contain enough signal for groundedness checks."
            accumulator.criterion_scores["groundedness"] = 1.0
            accumulator.score += 0.1
            return

        unsupported_terms = sorted(term for term in candidate_terms if term not in reference_terms)
        overlap_terms = sorted(term for term in candidate_terms if term in reference_terms)
        groundedness_score = len(overlap_terms) / (
            len(candidate_terms) + (2 * len(unsupported_terms))
        )

        accumulator.groundedness_score = round(groundedness_score, 4)
        accumulator.criterion_scores["groundedness"] = round(groundedness_score, 4)
        accumulator.unsupported_terms = unsupported_terms

        if unsupported_terms:
            accumulator.feedback_messages.append("Groundedness check found unsupported answer terms.")
            accumulator.groundedness_feedback = (
                f"Unsupported terms detected: {', '.join(unsupported_terms[:5])}."
            )
        else:
            accumulator.feedback_messages.append("Groundedness check found no unsupported answer terms.")
            accumulator.groundedness_feedback = "All significant answer terms were grounded in the reference."

        if groundedness_score < 0.5:
            accumulator.score = max(0.0, accumulator.score - 0.1)
        accumulator.score += 0.1 * groundedness_score

    @staticmethod
    def _extract_terms(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{4,}", text.lower())
            if token not in {"issue", "summary", "response", "result"}
        }


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: list[BaseEvaluator] = []

    def register(self, evaluator: BaseEvaluator) -> None:
        self._evaluators.append(evaluator)

    def definitions(self) -> list[dict[str, str]]:
        return [
            {
                "name": evaluator.name,
                "kind": evaluator.kind,
            }
            for evaluator in self._evaluators
        ]

    def evaluate(self, context: ScoreContext) -> ScoreAccumulator:
        accumulator = ScoreAccumulator()
        for evaluator in self._evaluators:
            evaluator.evaluate(context, accumulator)
        return accumulator


def build_default_registry() -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    registry.register(KeywordEvaluator())
    registry.register(ReferenceOverlapEvaluator())
    registry.register(RubricCoverageEvaluator())
    registry.register(StructuredOutputEvaluator())
    registry.register(GroundednessEvaluator())
    return registry
