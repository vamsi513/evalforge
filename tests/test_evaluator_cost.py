"""
tests/test_evaluator_cost.py — Regression coverage for the heuristic-cost bug.

EvalRunner (app/engine/evaluator.py) is the pure heuristic scorer — it never
makes an LLM call, so it has no real API spend to report. A prior fix
(07ae123 "fix heuristic cost to zero") patched judge.py's mock judge path,
but EvalRunner's own cost_usd was still a token-count-derived estimate that
displayed as genuine "Judge API spend" on the live demo, which only ever
exercises this exact path.
"""

from app.engine.evaluator import EvalRunner
from app.models.eval_run import EvalRunCreate, EvalSample


def test_heuristic_run_reports_zero_cost():
    runner = EvalRunner()
    payload = EvalRunCreate(
        dataset_name="cost-regression-test",
        prompt_version="v1",
        model_name="heuristic-demo",
        samples=[
            EvalSample(
                prompt="What is the capital of France?",
                expected_keyword="Paris",
                candidate_output="The capital of France is Paris.",
            ),
            EvalSample(
                prompt="Name a primary color.",
                expected_keyword="red",
                candidate_output="Red is a primary color, along with blue and yellow.",
            ),
        ],
    )

    results, _ = runner.run(payload)

    assert len(results) == 2
    assert all(result.cost_usd == 0.0 for result in results)
