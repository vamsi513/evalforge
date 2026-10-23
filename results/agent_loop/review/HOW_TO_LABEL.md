# How to label the review sheet

The sheet holds 40 rows, 10 from each of the four task categories, drawn from
the development split only with a fixed seed. The sampler is given nothing but
task ids and their category, so no row is here because it failed.

Fill in four columns per row. Everything else is there to inform the judgment,
not to be edited.

The sheet deliberately shows you no rule result and no judge score. That is the
point: the agreement numbers are only meaningful if your label was formed
independently of the automation.

## What 40 rows costs

40 rows instead of 60 means every agreement figure is less certain. Cohen's
kappa on 40 paired labels has a noticeably wider bootstrap interval than on 60,
and the per category figures rest on 10 rows each, where a single disagreement
moves kappa a long way. Treat the per category numbers as indicative and the
overall figure as the one worth quoting. This is recorded in the limitations
section of agent_loop/README.md as well.

## human_correct

The overall verdict on whether the agent did the right thing for this task.
Use the `requirement` column as the standard.

- `pass` the response meets the requirement
- `fail` it does not
- `ambiguous` you genuinely cannot decide, or the task itself is unclear

`ambiguous` is not folded into pass or fail. It is reported separately and
excluded from the agreement statistics, so use it rather than guessing.

## human_faithful

Whether every specific claim is supported by `passages_shown`.

- `yes` every figure, name and date in the answer is in the passages
- `no` at least one specific claim is not supported, even if it is true
- `not_applicable` no passages were retrieved, so there is nothing to be
  faithful to. Typical for the direct route
- `ambiguous` you cannot tell

A correct answer can be unfaithful: if the agent stated a right figure that was
not in the passages it was shown, that is `human_correct=pass` and
`human_faithful=no`. Recording that combination is one of the more useful
things this sheet can surface.

## human_reasoning

Quality of the reasoning, separate from whether the final answer is right.

- `good` addresses the question directly and follows from the evidence
- `adequate` arrives somewhere reasonable but is vague, padded or partly off topic
- `poor` incoherent, evasive, or contradicts itself
- `ambiguous` you cannot tell

## human_notes

Free text. Worth using when you pick `ambiguous`, when correct and faithful
disagree, or when the task itself looks badly written. A note saying a task is
flawed is a useful result.

## Practical points

- Label every row. A blank `human_correct` counts as unlabelled, not as a pass.
- Values are lowercase and must match exactly. `Pass` is reported as an
  unrecognised value rather than counted, so it will not quietly become a
  disagreement.
- Save as CSV in place. Regenerating the sheet preserves your labels, backs up
  the previous file first, and clears only labels whose answer has changed.
