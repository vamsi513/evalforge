# Benchmark data

150 tasks for the AgentIQ failure loop, in `tasks.jsonl`, split into 90
development and 60 held out tasks by `split.json`.

## Where the tasks come from

AgentIQ answers from three sources and nothing else: a local FAISS corpus, live
Tavily web search, and the model's own knowledge on the direct route. So every
task here has to be answerable, or correctly refusable, from one of those three.
Anything else would measure my imagination rather than the agent.

The corpus is a single file in the AgentIQ repository,
`retrieval/documents/sample_docs.txt`, holding 30 documents in a
`===DOC_START=== / Title: / Source: / body / ===DOC_END===` format. They are all
ML and LLM topics: transformers, BERT, RAG, RLHF, embeddings, LangGraph,
chain of thought, GPT-4, agentic systems, LoRA, mixture of experts,
constitutional AI, CLIP, diffusion, FlashAttention, Llama 2, in-context
learning, function calling, RoPE, speculative decoding, quantization, graph
neural networks, code generation, autonomous agents, prompt engineering,
evaluation frameworks, semantic chunking, multi-agent systems, and AI safety.

I read all 30 documents before writing any task. Every retrieval answer below
was taken from a sentence in that file, and the `source_docs` field on each task
records which documents it came from. No facts were invented, and nothing was
added about real people beyond what the corpus itself states.

The corpus is the ground truth here, not the world. In at least one place it
differs from the published paper it cites: the graph neural network document
attributes 81.5 percent to Citeseer, 79.0 to Cora and 70.3 to Pubmed, where the
original GCN paper orders those differently. A retrieval task is scored against
what the corpus says, because that is what the agent can actually retrieve.

## Categories

| Category | Count | What it tests |
|---|---|---|
| `tool_selection` | 40 | Whether the router picks the right source. 14 should go to `retrieval`, 13 to `web_search`, 13 to `direct`. |
| `multi_step_retrieval` | 40 | Whether retrieval finds the right passages and the answer uses them. Most need two or three separate facts, several of them from two different documents. |
| `direct_no_tools` | 35 | Whether a question answerable from model knowledge is answered without reaching for a tool. |
| `unanswerable_decline` | 35 | Whether the agent declines instead of inventing. |

A few `tool_selection` tasks are deliberately awkward. `ts-023` asks which model
OpenAI released most recently: the subject is AI, which pulls toward
`retrieval`, but the answer is a recent event, which is `web_search`. Those
tasks exist to find router failures, not to be easy.

The `unanswerable_decline` set has four flavours:

- facts absent from a document that covers the topic (training cost, GPU count,
  learning rate, weight decay, random seed, layer count, validation loss)
- false premises about corpus content, where the right move is to correct the
  premise (`dec-005` Mixtral 8x22B, `dec-011` Stable Diffusion 3 FID,
  `dec-019` a GCN score that belongs to GAT, `dec-023` a 2015 Transformer,
  `dec-024` Gemini 2.5 Pro, `dec-025` a separate draft model for Medusa, which
  the document says Medusa does away with, `dec-030` Groq, `dec-034` the EU AI Act)
- attribution questions, where the fact exists but in a different document
  (`dec-016` asks what the RLHF document says about DPO, which is in the AI
  safety document)
- things no tool can reach: the user's name, their bank balance, a previous
  day's conversation, this server's filesystem paths

`dec-027` is a partial answer task. The BERT document says eleven benchmarks and
names two of them. Naming those two and saying the other nine are not listed is
correct. Naming nine more is a failure.

I kept live-information questions out of the decline set on purpose. A price or
a current rate is a legitimate `web_search`, not something to refuse, so putting
one there would have scored a correct answer as a failure.

## Task schema

Every line has the same eight fields.

| Field | Meaning |
|---|---|
| `id` | Stable identifier. Prefixes: `ts`, `msr`, `dnt`, `dec`. |
| `category` | One of the four above. |
| `question` | What is sent to the agent, verbatim. |
| `expected_route` | `retrieval`, `web_search`, `direct`, or null when any route could be legitimate. |
| `expected_answer` | Null, or `{"required": [[...], [...]]}`. Each inner list is one required fact and its acceptable surface forms. All groups must match; within a group any one form will do. |
| `expected_behavior` | Null, or prose stating what a correct response has to do. Used where there is no string to match, mainly declines and greetings. |
| `must_not_contain` | Reserved for strings that would indicate fabrication. Empty everywhere today; decline detection is handled by rule, judge and human review instead. |
| `source_docs` | Exact corpus titles the answer was drawn from. |

Loading is validated in `agent_loop/tasks.py`. A task with no check at all, a
duplicate id, an unknown category or route, or a malformed `expected_answer` is
a load error rather than something discovered mid run.

### Why the matching is deliberately blunt

`expected_answer` matching lowercases, folds dash and quote variants, and
ignores digit group separators, so "4,096" and "4096" are the same answer and
"T5-XXL" matches whichever dash came back. Terms of three characters or fewer,
and purely numeric terms, match on word boundaries, so a required "8" is not
satisfied by "48" and a required "0.25" is not satisfied by "10.25".

This catches whether the right number is present. It cannot tell whether the
sentence around the number is true, which is exactly why there are two more
judging layers.

`source_docs` holds corpus titles exactly as the corpus writes them, em dashes
included, because the agent returns those strings in `sources[].title` and the
retrieval rule check compares against them. Everywhere else in this folder the
prose avoids em and en dashes.

## The split

`split.json` is written by `python -m agent_loop.scripts.make_split`.

- seed `20261022`, fixed
- 90 development, 60 held out
- stratified by category: development gets 24 tool selection, 24 multi step
  retrieval, 21 direct, 21 decline; held out gets 16, 16, 14, 14
- allocation uses largest remainder so the counts sum exactly rather than
  drifting through rounding
- shuffling runs over an id-sorted copy of each category, so re-ordering lines
  in `tasks.jsonl` cannot move a task between sides

`split.json` also records the SHA-256 of `tasks.jsonl`. A split only means
something relative to the exact task list it was drawn from, and the hash is
what makes a changed benchmark visible instead of silent.
`python -m agent_loop.scripts.make_split --check` verifies the two still agree
and writes nothing.

## Held out discipline

The held out 60 are scored exactly twice: once before the fix and once after.

I do not read held out failures, I do not cluster them, and no task wording or
fix is changed once a held out number exists. Failure analysis and the design of
the fix use the 90 development tasks only. If the fix does not help, that is the
result.
