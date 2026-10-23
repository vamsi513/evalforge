# Development failure taxonomy

9 failures across 90 development tasks, from the `dev_baseline` run.

Union of layer 1 rule failures across all development tasks and human failures on the subset that was labelled.

Clusters are assigned from trace evidence. The decisive test for a missing fact is whether that fact appears in the passages the agent was actually shown, which separates a retrieval problem from a generation problem.

## Counts

| Cluster | Failures | Caught by rules | Caught by judge | Human called fail |
|---|---|---|---|---|
| `retrieval_miss` | 4 | 4/4 | 3/4 | 1/1 |
| `ignored_retrieved_evidence` | 2 | 2/2 | 1/2 | 1/1 |
| `direct_answer_error` | 1 | 1/1 | 1/1 | 1/1 |
| `failure_to_decline` | 1 | 0/1 | 1/1 | 1/1 |
| `unverifiable_live_answer` | 1 | 0/1 | 1/1 | 1/1 |

Judge and human columns are over the subset each layer actually saw: every failure was judged, but only the 40 row review sample was labelled.

## retrieval_miss (4)

The route was right and the agent behaved sensibly, but the passage holding the required fact was never retrieved, so the agent reported that its context did not contain the answer. The fact is in the corpus.

By category: multi_step_retrieval 4

Task ids: msr-022, msr-031, msr-039, msr-040

### `msr-022`

**Question.** What speedup does FlashAttention-2 give at sequence length 8K, and what RoPE base frequency does Llama 3 use?

**Route taken.** `retrieval`

**Answer excerpt.**

> The context does not provide specific information about the speedup that **FlashAttention-2** gives at a sequence length of **8K**. It mentions that **FlashAttention** enables training on significantly longer sequences and targets **H100 hardware**, achieving **740+ TFLOPs/s for FP16**, but does not

**Required but absent from the answer.** 9x or 9 times

**Was it in the retrieved passages?** No. The agent could not have answered from what it was given.

**Documents retrieved.** FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness, Rotary Position Embeddings (RoPE) and Long Context Extension in LLMs, Code Generation with LLMs: Codex, CodeLlama, and Programming Assistants

### `msr-031`

**Question.** According to the evaluation frameworks document, what MMLU scores do GPT-3 175B, GPT-4 and Llama 3 70B Instruct reach?

**Route taken.** `retrieval`

**Answer excerpt.**

> The context provided does not include specific MMLU scores for GPT-3 175B, GPT-4, or Llama 3 70B Instruct. It discusses various evaluation frameworks and methodologies but does not detail the scores for these specific models. Therefore, I cannot answer the question regarding their MMLU scores from t

**Required but absent from the answer.** 43.9; 86.4; 82.0

**Was it in the retrieved passages?** No. The agent could not have answered from what it was given.

**Documents retrieved.** GPT-4 Technical Report — Capabilities and Safety, LLM Evaluation Frameworks: HELM, BIG-Bench, and MMLU Benchmarks, Code Generation with LLMs: Codex, CodeLlama, and Programming Assistants

### `msr-039`

**Question.** What expected calibration error does GPT-4 achieve, and what does LLaMA 2 70B achieve?

**Route taken.** `retrieval`

**Answer excerpt.**

> The provided context does not include information about the **expected calibration error** for either **GPT-4** or **LLaMA 2 70B**. It covers various capabilities and performance metrics for GPT-4, such as its scores on professional and academic benchmarks, but does not mention calibration error. Si

**Required but absent from the answer.** 0.05; 0.19

**Was it in the retrieved passages?** No. The agent could not have answered from what it was given.

**Documents retrieved.** GPT-4 Technical Report — Capabilities and Safety, Quantization for LLMs: GPTQ, QLoRA, and INT8 Inference Techniques, Code Generation with LLMs: Codex, CodeLlama, and Programming Assistants

_1 further case(s) in the JSON companion._

## ignored_retrieved_evidence (2)

The required fact was present in the passages the agent was shown, and the answer still failed to state it.

By category: multi_step_retrieval 2

Task ids: msr-012, msr-017

### `msr-012`

**Question.** What quantization data type does QLoRA use, and approximately how many bits per weight does double quantization save?

**Route taken.** `retrieval`

**Answer excerpt.**

> **QLoRA** uses **4-bit quantization** of the base model. According to the context, **double quantization** saves approximately **0.37 bits per weight**.

**Required but absent from the answer.** nf4 or normalfloat

**Was it in the retrieved passages?** Yes: nf4 or normalfloat. The agent had it and did not use it.

**Documents retrieved.** Quantization for LLMs: GPTQ, QLoRA, and INT8 Inference Techniques, Quantization for LLMs: GPTQ, QLoRA, and INT8 Inference Techniques, Llama 2: Open Foundation and Fine-Tuned Chat Models from Meta AI

### `msr-017`

**Question.** What is the context window of Llama 2 and what was the context window of Llama 1?

**Route taken.** `retrieval`

**Answer excerpt.**

> The context window of **Llama 2** is **4K tokens**. However, the provided context does not specify the context window of **Llama 1**. Therefore, I cannot answer the rest regarding Llama 1's context window from the available documents.

**Required but absent from the answer.** 4096 or 4,096; 2048 or 2,048

**Was it in the retrieved passages?** Yes: 4096 or 4,096. The agent had it and did not use it.

**Documents retrieved.** Rotary Position Embeddings (RoPE) and Long Context Extension in LLMs, Code Generation with LLMs: Codex, CodeLlama, and Programming Assistants, FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness

## direct_answer_error (1)

No retrieval involved. The agent answered from its own knowledge and got it wrong.

By category: direct_no_tools 1

Task ids: dnt-026

### `dnt-026`

**Question.** Spell the word necessary backwards.

**Route taken.** `direct`

**Answer excerpt.**

> The word "necessary" spelled backwards is "yssarenec."

**Required but absent from the answer.** yrassecen

**Was it in the retrieved passages?** No. The agent could not have answered from what it was given.

## failure_to_decline (1)

The question could not be answered from the evidence and the agent answered anyway, instead of saying so or correcting the premise. Where `missed_by_decline_rule` is set, layer 1 passed the row because refusal phrasing appeared somewhere in the answer while the answer still supplied the information: the detector failed, not just the agent.

By category: unanswerable_decline 1

Task ids: dec-028

### `dec-028`

**Question.** What is the per-token inference cost of running Mixtral on AWS?

**Route taken.** `web_search`

**Answer excerpt.**

> The **per-token inference cost** of running **Mixtral 8x7B** on **Amazon AWS** is **$0.450 per 1 million input tokens**. This pricing is consistent across the tracked pricing mode for this model, as stated in the context from [Source 1].   Additionally, it is noted that the **lowest output token pri

**Evidence.** `{"route": "web_search", "missed_by_decline_rule": true, "matched_phrases": ["the context does not"]}`

## unverifiable_live_answer (1)

A live web question where the answer cannot be checked against anything in the trace, or the agent returned conflicting values.

By category: tool_selection 1

Task ids: ts-026

### `ts-026`

**Question.** What time does the sun set in Seattle today?

**Route taken.** `web_search`

**Answer excerpt.**

> The sunset time in Seattle today varies slightly across different sources:  - According to [Source 1], the sunset is at **6:13 PM**. - [Source 2] states the sunset is at **6:09 PM**. - [Source 3] indicates the sunset is at **6:08 PM**. - [Source 4] mentions the sunset at **6:10 PM**.  The context do

**Evidence.** `{"sources_returned": 5, "route": "web_search"}`

