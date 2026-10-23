# Agent failure loop

Evaluate the AgentIQ research agent, find where it fails from its own execution
traces, apply one targeted fix, and measure whether the fix helped on tasks held
out from the analysis.

**Headline result: the fix did not help.** On the 60 held out tasks the
deterministic measure was 55/60 before and 55/60 after, with zero tasks changing
verdict in either direction. That is the finding, and it is reported as it came
out.

This folder is additive. It reads AgentIQ through its public graph API and
reuses EvalForge's judge and statistics. It modifies neither project. Every
number below is traceable to a file under `results/agent_loop/`.

## What was measured

150 tasks in four categories, split 90 development and 60 held out with a fixed
seed. Development was used to find failures and design the fix. Held out was
scored exactly twice: once before the fix, once after.

| | Development (90) | Held out before (60) | Held out after (60) |
|---|---|---|---|
| Layer 1 overall | 83/90, 92.2% | 55/60, 91.7% | 55/60, 91.7% |
| tool selection | 24/24, 100% | 16/16, 100% | 16/16, 100% |
| multi step retrieval | 18/24, 75.0% | 12/16, 75.0% | 12/16, 75.0% |
| direct, no tools | 20/21, 95.2% | 14/14, 100% | 14/14, 100% |
| unanswerable, decline | 21/21, 100% | 13/14, 92.9% | 13/14, 92.9% |

`results/agent_loop/scores/*_rules.json`

The router never misrouted once in 90 development tasks or 60 held out tasks.
Every failure was answer content. AgentIQ has no dynamic tool calling, so
"tool selection" here means routing between three fixed sources.

## Three judging layers

**Layer 1, rules.** Route against the task's expected source, normalised answer
matching, decline detection, a per route latency budget, and an error check that
reads the graph state's `error` key. Deterministic.

**Layer 2, judge.** EvalForge's `JudgeClient` on `claude-haiku-4-5`, a different
model family from the agent's `gpt-4o-mini`, scoring reasoning quality and
faithfulness against the passages the agent actually retrieved. On development it
passed 65/90, 72.2%, markedly stricter than the rules.

**Layer 3, human.** 40 development runs, 10 per category, labelled blind. No rule
verdict, no judge score and no suggested label in the sheet.

## Judge and rule agreement with the human

40 rows labelled, 3 excluded as ambiguous, 37 compared.

| Comparison | Agreement | Kappa | 95% CI |
|---|---|---|---|
| rule vs human | 94.6% | 0.7218 | [0.0, 1.0] |
| judge vs human | 83.8% | 0.5394 | [0.2128, 0.8263] |
| rule vs judge | 78.4% | 0.3451 | [0.0, 0.6542] |

Excluding 4 rows whose automated verdict the annotator had already seen, n = 33:

| Comparison | Agreement | Kappa | 95% CI |
|---|---|---|---|
| rule vs human | 93.9% | 0.0 (degenerate) | [0.0, 1.0] |
| judge vs human | 81.8% | 0.3356 | [0.0, 0.7179] |
| rule vs judge | 75.8% | 0.0 (degenerate) | [0.0, 0.0] |

`results/agent_loop/agreement/dev_baseline_agreement.json`

Two of those numbers are traps and the script labels them as such. The
rule-versus-human kappa has an interval spanning the whole range, so it says
nothing about the true value. The 0.0 entries are degenerate rather than damning:
the rule layer passed every one of the 33 remaining rows, and a rater who never
varies scores kappa 0 however often it agrees. The confusion counts are the
honest reading, and they carry the real finding: excluding flagged rows,
`both_fail` is 0 of 33 for rule versus human. Every failure the rules correctly
caught in the review sample was on a row the annotator had already been told
about. The judge is stricter than the human in one direction only: 6 rows it
failed and the human passed, 0 the other way.

Where a layer is unreliable: judge versus human on `direct_no_tools`, kappa 0.2
on 10 rows.

The 3 ambiguous rows are all live web questions, each annotated with the same
reason: no passages are shown, so the claim cannot be independently verified.
That is a real gap rather than indecision. A web search answer leaves nothing in
the trace to check it against.

## The failure taxonomy

9 failures across the 90 development tasks, taken as the union of layer 1
failures and human failures rather than the rule verdict alone, so failures the
rules cannot see still inform the choice of fix.

| Cluster | Failures | Rules caught | Judge caught | Human called fail |
|---|---|---|---|---|
| `retrieval_miss` | 4 | 4/4 | 3/4 | 1/1 |
| `ignored_retrieved_evidence` | 2 | 2/2 | 1/2 | 1/1 |
| `direct_answer_error` | 1 | 1/1 | 1/1 | 1/1 |
| `failure_to_decline` | 1 | 0/1 | 1/1 | 1/1 |
| `unverifiable_live_answer` | 1 | 0/1 | 1/1 | 1/1 |

`results/agent_loop/failure_taxonomy.md`, with three quoted excerpts per cluster.

Clusters are assigned from trace evidence. The decisive test is whether the fact
the answer lacked appears in the passages the agent was shown, which separates a
retrieval problem from a generation problem. Those two are identical in an
accuracy number and need opposite fixes.

## The fix

**Target: `retrieval_miss`**, the largest cluster at 4 of 9. With
`ignored_retrieved_evidence`, 6 of 9 failures sit on the retrieval path. In every
`retrieval_miss` case the agent routed correctly, searched the corpus, and
reported that its context did not contain the answer, while the fact was in the
corpus.

**A candidate rejected at development validation.** The first attempt was
AgentIQ's own `ENABLE_QUERY_REWRITING`, a retrieval setting applied from outside
the agent. On 90 development tasks it fixed nothing: the retrieved context was
byte for byte identical on all six retrieval failures. `retriever_node` merges
the paraphrase results and then cuts to the best 3 chunks by score, and the
original phrasing's chunks already scored highest, so the paraphrases cost one
extra model call per retrieval run and changed nothing. Development accuracy went
83/90 to 82/90. Recorded in `variants.py` as `query_expansion` so the rejection
is reproducible.

**The fix: a sub question retrieval guard.** The corpus is 50 chunks and the
retriever keeps 3. The failing questions are multi part, asking for two or three
facts that live in different chunks, and a single embedding of the whole question
matches the average of those parts rather than any one of them. The guard runs
the question normally, and if the agent took the retrieval route and reported
missing evidence, it decomposes the question into standalone sub questions, runs
each through the same graph, and presents the sub answers together.

The mechanism was verified before anything was built, by querying FAISS directly:
per sub question retrieval surfaced facts the whole question missed on three of
three failures tested. The retry decision uses only the agent's own output, never
anything from the task definition, so it is something the system could do in
production. AgentIQ is unchanged.

**Development validation:** 83/90, unchanged overall. `msr-022` and `msr-039`
fixed, `dec-024` broken, and `dec-028` flipped for a reason that is not the fix:
it gave AWS pricing figures in all three runs including baseline, and the baseline
only passed because the decline regex matched that run's wording. The human label
also called `dec-028` a failure. So the attributable development effect is +2
retrieval, −1 decline. The guard fired on 11 of 90 tasks and cost 39 percent more
than baseline, with mean latency up 7 percent.

## Held out result

The guard fired on 9 of the 60 held out tasks: all 4 retrieval failures, and 5
decline tasks that were already passing.

**Primary measure, layer 1 rules:**

| | Before | After | Difference |
|---|---|---|---|
| Overall | 55/60, 91.7% | 55/60, 91.7% | 0.0000, 95% CI [0.0000, 0.0000] |
| tool selection | 16/16 | 16/16 | 0.0000 |
| multi step retrieval | 12/16 | 12/16 | 0.0000 |
| direct, no tools | 14/14 | 14/14 | 0.0000 |
| unanswerable, decline | 13/14 | 13/14 | 0.0000 |

Paired exact McNemar: 0 fixed, 0 broken, 0 discordant pairs, p = 1.0. The
interval is zero width because no task changed verdict, so every bootstrap
resample is identical. No category got worse.

The guard fired on all four held out retrieval failures and fixed none of them.
On development it fixed 2 of 5 comparable cases. The difference between those two
outcomes is small sample variation, not a mechanism.

**Secondary measure, judge:** 45/60 to 40/60, difference −0.0833, 95% CI
[−0.1667, 0.0000], McNemar 1 fixed and 6 broken, p = 0.125.

That looks like a regression and mostly is not one. Five of the seven judge
verdict flips were on tasks the guard never fired on, and four of those had a
byte for byte identical answer in both runs. Quantified across the held out set:

| | Judge | Rules |
|---|---|---|
| Verdict flips on byte-identical answers | 4 of 19, **21.1%** | 0 of 19 |

Mean absolute judge score drift on identical input was 0.071, maximum 0.25, with
scores clustering at 0.50 and 0.75 either side of the judge's own 0.7 pass
threshold. The judge is not stable enough at that threshold to measure an effect
of this size. What is attributable to the guard is `dec-015` and `dec-025`, two
decline tasks where the sub answers supplied information the refusal had withheld
and the judge dropped them from 0.92 to 0.15 and 0.35. That is the same
regression mechanism `dec-024` showed on development.

`results/agent_loop/comparison/heldout_comparison.json`

## What this says

The fix did not work. It fired where it was designed to fire, on every retrieval
failure in the held out set, and changed no outcome. The honest reading is that
`retrieval_miss` is not fixable from outside the agent: the binding constraint is
`retriever_node` keeping 3 chunks of 50, hardcoded, and no wrapper level setting
or guard can widen it. Both candidate fixes failed for that same reason, one by
being inert and one by retrieving better without that reaching the answer.

The second finding is about measurement rather than the agent. A judge with a
21 percent verdict flip rate on identical input cannot measure a several point
accuracy difference, and the deterministic rules, which agreed with the human on
94.6 percent of reviewed rows, are the measure to trust here. Had the judge been
the primary measure, this run would have reported a significant regression that
the evidence does not support.

## Cost

$0.9666 against a $1.50 cap, across 12 recorded batches, in
`results/agent_loop/cost_ledger.jsonl`.

| | Batches | Billed units | Cost |
|---|---|---|---|
| Agent runs | 8 | 404 runs | $0.0990 |
| LLM judge | 6 | 220 judgments | $0.8677 |
| Tavily web search | | ~90 calls | $0 on the free tier |
| **Total** | **12 ledger rows** | | **$0.9666** |

Billed agent runs, 404, exceed the 390 tasks actually evaluated, because a
guarded run makes additional sub question calls that are charged to it.

Judge calls were 90 percent of the spend and produced the less reliable of the
two measures. $0.0282 of that went on judge probes, $0.0127 of which was a
probe whose judgments were discarded as invalid, quarantined in
`results/agent_loop/scores/superseded/` with the reason.

## Layout

| Path | What it is |
|---|---|
| `data/tasks.jsonl` | 150 tasks, four categories |
| `data/split.json` | seeded 90 / 60 split with the task file hash |
| `data/README.md` | how the tasks were built and from what |
| `tasks.py` | schema, loader, normalised answer matching |
| `splitting.py` | seeded splitting and sampling |
| `credentials.py` | key loading, imports nothing from either project |
| `runner.py` | one agent run, full trace capture, the guarded run path |
| `variants.py` | wrapper configurations, including the rejected candidate |
| `guards.py` | the sub question guard |
| `rules.py` | layer 1 |
| `judging.py` | layer 2 |
| `review_sheet.py` | layer 3 blind export |
| `metrics.py` | agreement and paired comparison statistics |
| `scripts/` | runnable entry points |
| `tests/` | 156 tests |

## How to run it

AgentIQ must be importable and EvalForge must be the working directory. That
order matters: AgentIQ has an `app.py` at its root which shadows EvalForge's
`app/` package.

```bash
cd /path/to/evalforge
export PYTHONPATH=/path/to/agentiq
python -m agent_loop.scripts.make_split
python -m agent_loop.scripts.run_agent --split dev --mock           # free
python -m agent_loop.scripts.run_agent --split dev --variant baseline
python -m agent_loop.scripts.score_runs --label dev_baseline --rules-only
python -m agent_loop.scripts.score_runs --label dev_baseline        # adds the judge
python -m agent_loop.scripts.make_review_sheet --label dev_baseline
python -m agent_loop.scripts.merge_labels --label dev_baseline --labels-csv <filled.csv>
python -m agent_loop.scripts.agreement --label dev_baseline
python -m agent_loop.scripts.failure_taxonomy --label dev_baseline
python -m agent_loop.scripts.compare_heldout --before heldout_before --after heldout_after
```

Keys are read from `~/.agent_loop.env`, outside any repository. Every paid batch
appends to the ledger, and a run refuses to start or aborts mid sweep once the
ledger plus the current batch would cross `--max-total-usd`.

## What is reused rather than rebuilt

- `app/engine/judge.py` and `app/models/eval_run.py`: the whole layer 2 judge,
  its Anthropic structured output path and its token based cost accounting.
- `_TOKEN_PRICING_USD` from the same module, so there is one price table.
- `scripts/analyze_judge_agreement.py`: `_cohens_kappa`, `_bootstrap_ci`,
  `_pearson_r` and the repository's 0.7 pass threshold.
- `scripts/analyze_privacy_results.py` and `tests/test_privacy_review_csv.py` as
  the pattern for blind review: blank label columns, carry forward keyed to the
  exact response, backups before regeneration, a closed label vocabulary.

`app/services/dataset_service.py` was read and not used: it is CRUD over a
dataset metadata table and stores no cases.

## Limitations

**One agent, one corpus.** AgentIQ on its own 30 document corpus, with no
dynamic tool calling. Nothing here transfers to an agent that composes arbitrary
tool calls.

**I wrote the tasks myself.** Grounded in the corpus and documented in
`data/README.md`, but a benchmark written by the person graded by it is not
independent. Where the corpus disagrees with the published literature the corpus
wins, because that is what the agent can retrieve.

**One annotator, who also wrote the tasks.** The agreement figures measure
agreement with one person's judgment, not with ground truth, and there is no
inter-annotator reliability estimate because there is no second annotator.

**The human sample is 40 rows.** 10 per category. Kappa on 40 paired labels
carries a wide bootstrap interval, and the per category figures rest on 10 rows
each where one disagreement moves kappa a long way. The per category numbers are
indicative; the overall figure is the one worth quoting. The intervals are
reported so this is visible rather than buried.

**Blindness was partly compromised.** Four of the 40 reviewed rows had their
automated verdict disclosed to the annotator in an earlier progress report,
before labelling: `dnt-004`, `dnt-026`, `msr-017`, `msr-022`. Those rows are
marked in the sheet and every agreement figure is reported both with and without
them. The sheet itself carries no verdicts and the sample was drawn without
reference to any outcome, but the disclosure happened and cannot be withdrawn.

**Agent side token costs are estimates.** AgentIQ constructs `ChatOpenAI` with
`streaming=True`, so the provider reports no usage on `invoke`. Agent costs are
tiktoken counts plus the documented chat envelope, which biases them high. Every
trace records `usage_source`. Judge costs are provider reported.

**Decline detection is a regex, and it is unstable.** `dec-028` passed in one run
and failed in the next two on effectively the same wrong behaviour, purely
because the phrasing moved. Any decline figure here has that noise in it.

**Faithfulness is judged against truncated context.** `EvalSample` caps
`reference_answer` at 2000 characters; 56 of the 90 development judgments were
truncated, so the judge often saw less than the agent did. Each judgment records
its own truncation flag.

**The judge is not stable at its threshold.** 21.1 percent verdict flip rate on
byte-identical input. It is reported as a secondary measure for that reason.

**Small samples throughout.** 90 development and 60 held out. A held out
difference of a few tasks is indistinguishable from noise, which is why the
comparison is reported with a paired McNemar test and a bootstrap interval rather
than as two accuracy numbers.

**One fix, one shot.** The brief allowed a single targeted fix. A different
cluster, or a change inside AgentIQ's retriever, might well have worked. Neither
was tried.

## Next steps

- The binding constraint is `retriever_node` keeping 3 of 5 chunks, hardcoded. A
  change inside AgentIQ to make that configurable is the obvious experiment, and
  is outside what this exercise was allowed to touch.
- Replace the decline regex with something stable before any decline number is
  quoted again.
- The judge needs either a calibrated threshold or repeated sampling with a
  majority vote before it can measure differences of this size.
- Web search answers leave nothing in the trace to verify them against, which is
  what made 3 rows unlabelable. Capturing the retrieved web passages would close
  that.
