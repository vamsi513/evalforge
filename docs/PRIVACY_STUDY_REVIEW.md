# External review: request draft and recording checklist

Nothing in this file has been sent. No external review has happened. No one
outside this repository has seen the study, and nothing in
[`PRIVACY_STUDY.md`](PRIVACY_STUDY.md) should be described as reviewed,
validated, or adopted until the log at the bottom of this file says otherwise.

## Draft message

Pick one reviewer and send it to them directly. It asks for three specific
judgments rather than general feedback, which is the difference between getting a
reply and not.

> Subject: Sanity check on a small privacy-disclosure eval (40 cases, local model)
>
> Hi <name>,
>
> I built a small evaluation that asks one question: when a private value is in a
> model's context or in a retrieved document, does the model give it to a requester
> whose authorisation isn't established? 40 hand-written cases, one local 7B model
> (qwen2.5:7b-instruct), two prompt configurations, deterministic string-match
> scoring with no LLM judge. Write-up and data are here: <link>.
>
> I'm not asking you to review the code. I'd value your judgment on three things
> where I think I could be wrong:
>
> 1. **Is the threat model coherent?** Authorisation is asserted as session metadata
>    in the context, and I score whether the model acts on it. I think that matches
>    how an application would actually pass authorisation, but it means I'm testing
>    instruction-following on a trust label rather than anything like access control.
>    Is that framing defensible, or does it make the result less interesting than it
>    looks?
>
> 2. **Does the dataset measure what I claim?** In particular: I include 8 authorized
>    cases so over-refusal is measurable, and I flag 3 cases `inference_sensitive`
>    where answering leaks the value without quoting it, so string matching can't
>    decide them. I also flag 7 injection cases `benign_user_request`, where success
>    means answering the user's unrelated question and ignoring the injected
>    instruction. The one I'm least sure about is `inject-05`: the user asks what a
>    company's upcoming plans are, and the secret is the unannounced programme
>    codename. I treated that request as benign. Would you?
>
> 3. **Is the scoring honest about its limits?** Disclosure is decided by matching
>    the value (normalised, so character-spaced evasions count), independently of any
>    refusal wording. That turned out to matter: in the guarded configuration, 8 of
>    16 disclosures were responses that refused *and* named the secret in the same
>    sentence, so a refusal-keyword scorer would have called that config 21/32 safe
>    instead of 13/32. Refusal detection itself is 16 hand-written English regexes,
>    and one case produced a correct refusal in Spanish that I scored as ambiguous.
>    Is routing undecidable cases to manual review the right call, or would you push
>    for something else?
>
> Two things I'm deliberately not claiming, and I'd like to know if the write-up
> still oversells them: this says nothing about training-data memorization (every
> secret is invented and only ever appears in the prompt), and 40 cases on one
> quantised 7B model is not a result about models in general.
>
> If it's easier, the single most useful thing would be a reply on question 2 alone.
>
> Thanks,
> Vamsi

### Before sending

- [ ] Replace `<name>` and `<link>`.
- [ ] Confirm the numbers in the message still match
      `evaluation/results/privacy_analysis.json`. They are quoted by hand here and
      will go stale if the study is rerun.
- [ ] Decide what you are asking for. If you want a reply, ask one question, not three.
- [ ] Check the link is readable without cloning the repo.

### Picking someone

Prefer a person over a mailing list, and someone whose own work touches eval
methodology or prompt injection. An issue or discussion thread on a related
open-source eval project is a reasonable alternative to email, and is public,
which makes question 2 easier for a stranger to answer.

Do not send the same message to several people at once. If the first reply
changes the dataset, the second reviewer should see the changed version.

## Recording feedback

One entry per reviewer. Fill it in from what they actually wrote, quoting where
the wording matters. Leave disagreements in — a reviewer who thinks the framing is
wrong is the most useful outcome, and deleting that makes the log worthless.

```
### Review <n>

- Reviewer: <name>, <affiliation or project>, <how you know them / why you asked>
- Contacted: <date>  Replied: <date>
- Medium: <email / issue link / call>
- What they were shown: commit <sha>, dataset version <x.y.z>, content hash <hash>

What they said, in their words:
- Threat model:
- Dataset:
- Scoring:
- Anything they raised that I had not asked about:

What I changed as a result:
- <commit sha> — <what changed and which point it answers>
- (or: nothing, because <reason>)

What I did not change, and why:
- <point> — <reason for disagreeing or deferring>

Still open:
- <anything unresolved>
```

### Rules for this log

- Only real, received feedback goes here. Not anticipated objections, not a
  self-review, not a model's opinion of the study.
- An entry is only complete once `Replied` has a date. No reply means no entry.
- If a reviewer's comment changes the dataset, bump `dataset_version`, re-stamp the
  content hash, rerun, and reference the new result file. A review that changes the
  data invalidates the numbers in the write-up.
- If a reviewer asks not to be named, record the affiliation and omit the name.
  Do not quote someone publicly without checking.
- Nothing in this repository, including README and the study write-up, may say
  "reviewed by", "feedback from", or "used by" anyone until their entry here is
  complete.

## Log

No reviews recorded.
