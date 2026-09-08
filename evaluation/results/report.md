# Judge evaluation report

Generated 2026-09-08T23:22:59.276837+00:00 from files in `evaluation/results/`. Every number below is read directly from a saved run's output, not retyped by hand.

## Dataset

- Version: `1.1.0` (content hash `30d94e4ac8b03154`)
- 60 hand-authored cases across 3 categories: general (20), support (20), code (20)
- Judge prompt fingerprint at benchmark time: `n/a`

This is a small, hand-written benchmark for comparing judge providers on the same 60 cases -- not a comprehensive evaluation suite.

## Per-provider results

| Provider | Model | n | Avg score | 95% CI | Avg latency (ms) | Total cost |
|---|---|---|---|---|---|---|
| openai | gpt-4o-mini | 60 | 0.645 | [0.5483, 0.7417] | 1529 | $0.006674 |
| anthropic | claude-haiku-4-5 | 60 | 0.634 | [0.5417, 0.7267] | 4162 | $0.184357 |
| mistral | — | 0 | — | — | — | 0 real calls (no successful (non-fallback) calls) |
| ollama | qwen2.5:7b-instruct | 60 | 0.715 | [0.6417, 0.7817] | 6076 | local inference, no per-request API charge |

Total real spend across paid providers this run: $0.191031.

## Local judge vs. paid providers: agreement

Pass/fail agreement and Cohen's kappa, computed on the 60 shared cases (threshold: score >= 0.7, same threshold the judge itself uses to set `passed`).

| Comparison | n | % Agreement | Cohen's kappa | Pearson r (raw scores) |
|---|---|---|---|---|
| ollama vs anthropic | 60 | 91.7% | 0.8223 | 0.8236 |
| ollama vs openai | 60 | 93.3% | 0.8592 | 0.7858 |

## Position-bias test

15 hand-authored pairs (each with one clearly better and one clearly worse response to the same prompt), tested with the local judge in both orders.

- Verdict flipped on swap: 0/15 (0.0%)
- Accuracy picking the better response, normal order: 100.0%
- Accuracy picking the better response, swapped order: 100.0%

These pairs were deliberately unambiguous (correct vs. clearly wrong), so a 0% bias rate here shows no bias on easy calls -- it doesn't establish anything about close judgment calls.

## What this does and doesn't show

- 60 cases is enough to get a first read on agreement, not a statistically definitive claim -- the bootstrap CIs above show real overlap between providers' average scores at this sample size.
- No human-labeled baseline is included in this report (that stage was skipped this round).
- Mistral is excluded from the agreement table: all 60 calls (and a second, more slowly paced retry) failed with rate limiting rather than returning real results.

