import { NextResponse } from "next/server";

const BASE = process.env.EVALFORGE_API_URL ?? "http://23.21.42.197:8001";
const KEY = process.env.EVALFORGE_API_KEY ?? "";

const DEMO_SAMPLES = [
  {
    prompt: "What is the capital of France?",
    expected_keyword: "Paris",
    candidate_output: "The capital of France is Paris, known for the Eiffel Tower.",
    reference_answer: "Paris is the capital and largest city of France.",
    scenario: "factual",
    slice_name: "geography",
    severity: "medium",
    required_json_fields: [],
    rubric: [],
  },
  {
    prompt: "What is 2 + 2?",
    expected_keyword: "4",
    candidate_output: "2 + 2 equals 4.",
    reference_answer: "The answer is 4.",
    scenario: "math",
    slice_name: "arithmetic",
    severity: "low",
    required_json_fields: [],
    rubric: [],
  },
  {
    prompt: "Who wrote Romeo and Juliet?",
    expected_keyword: "Shakespeare",
    candidate_output: "Romeo and Juliet was written by William Shakespeare.",
    reference_answer: "William Shakespeare wrote Romeo and Juliet.",
    scenario: "literature",
    slice_name: "authors",
    severity: "medium",
    required_json_fields: [],
    rubric: [],
  },
];

export async function POST() {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  try {
    // Ensure demo dataset exists
    await fetch(`${BASE}/api/v1/datasets`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        name: "live-demo",
        description: "Interactive demo dataset for EvalForge",
        owner: "demo",
      }),
    });

    // Submit the eval run
    const evalRes = await fetch(`${BASE}/api/v1/evals`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        dataset_name: "live-demo",
        model_name: "gpt-4o-mini",
        prompt_version: "demo-v1",
        evaluator_profile: "balanced",
        samples: DEMO_SAMPLES,
      }),
    });

    const text = await evalRes.text();
    let data: unknown;
    try { data = JSON.parse(text); } catch { data = { error: text }; }

    return NextResponse.json(data, { status: evalRes.status });
  } catch {
    return NextResponse.json({ error: "Demo unavailable" }, { status: 503 });
  }
}
