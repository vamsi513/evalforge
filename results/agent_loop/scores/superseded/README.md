# Superseded judge output

`dev_baseline_judgeprobe.json` was produced before a defect in this folder's
sample construction was fixed, and its judgments are not valid.

The defect: `judging.build_sample` passed the literal string "decline" as
`EvalSample.expected_keyword` for decline tasks. EvalForge's judge prompt
instructs the model to score the candidate against the expected keyword, so the
judge treated that word as a required string and marked down correct refusals
for not containing it. Two of the three probe rows failed for that reason.

Kept rather than deleted because it is the evidence for the defect, and because
the cost it incurred is recorded in the ledger. It must not be read as a
measurement of the agent.

Fixed in `agent_loop/judging.py`: the keyword now describes content a correct
answer would carry, and decline tasks get an `appropriate_refusal` rubric
criterion. Pinned by the regression tests in `agent_loop/tests/test_judging.py`.
The replacement probe is `dev_baseline_judgeprobe2.json`.
