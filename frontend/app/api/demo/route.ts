import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.EVALFORGE_API_URL ?? "http://23.21.42.197:8001";
const KEY = process.env.EVALFORGE_API_KEY ?? "";

const SCENARIOS: Record<string, { dataset: string; experiment: string; samples: unknown[] }> = {
  general: {
    dataset: "demo-general-knowledge",
    experiment: "General Knowledge",
    samples: [
      {
        prompt: "What is the capital of France?",
        expected_keyword: "Paris",
        candidate_output: "The capital of France is Paris, known for the Eiffel Tower.",
        reference_answer: "Paris is the capital and largest city of France.",
        scenario: "factual", slice_name: "geography", severity: "medium",
        required_json_fields: [], rubric: [],
      },
      {
        prompt: "What is 2 + 2?",
        expected_keyword: "4",
        candidate_output: "2 + 2 equals 4.",
        reference_answer: "The answer is 4.",
        scenario: "math", slice_name: "arithmetic", severity: "low",
        required_json_fields: [], rubric: [],
      },
      {
        prompt: "Who wrote Romeo and Juliet?",
        expected_keyword: "Shakespeare",
        candidate_output: "Romeo and Juliet was written by William Shakespeare.",
        reference_answer: "William Shakespeare wrote Romeo and Juliet.",
        scenario: "literature", slice_name: "authors", severity: "medium",
        required_json_fields: [], rubric: [],
      },
    ],
  },
  support: {
    dataset: "demo-customer-support",
    experiment: "Customer Support",
    samples: [
      {
        prompt: "How do I request a refund for my order?",
        expected_keyword: "refund",
        candidate_output: "To request a refund, go to your order history, select the order, and click 'Request Refund'. Refunds are processed within 5-7 business days.",
        reference_answer: "Customers can request refunds through order history within 30 days of purchase. Processing takes 5-7 business days.",
        scenario: "support", slice_name: "refunds", severity: "high",
        required_json_fields: [], rubric: [],
      },
      {
        prompt: "What is your shipping policy for international orders?",
        expected_keyword: "shipping",
        candidate_output: "International shipping takes 10-21 business days. We ship to over 50 countries. Customs fees may apply.",
        reference_answer: "International orders ship via standard carrier in 10-21 business days to 50+ countries. Import duties and customs fees are the customer's responsibility.",
        scenario: "support", slice_name: "shipping", severity: "medium",
        required_json_fields: [], rubric: [],
      },
      {
        prompt: "My account is locked. How do I regain access?",
        expected_keyword: "password",
        candidate_output: "If your account is locked, use the 'Forgot Password' link on the login page to reset your password via email.",
        reference_answer: "Locked accounts can be unlocked by resetting the password through the 'Forgot Password' flow on the login page.",
        scenario: "support", slice_name: "account", severity: "high",
        required_json_fields: [], rubric: [],
      },
    ],
  },
  code: {
    dataset: "demo-code-review",
    experiment: "Code & Tech",
    samples: [
      {
        prompt: "What does the 'async/await' pattern do in JavaScript?",
        expected_keyword: "asynchronous",
        candidate_output: "async/await is syntactic sugar for Promises that makes asynchronous code look synchronous, improving readability.",
        reference_answer: "async/await allows writing asynchronous code in a synchronous style using Promises under the hood.",
        scenario: "technical", slice_name: "javascript", severity: "medium",
        required_json_fields: [], rubric: [],
      },
      {
        prompt: "What is the time complexity of binary search?",
        expected_keyword: "O(log n)",
        candidate_output: "Binary search has a time complexity of O(log n) because it halves the search space with each step.",
        reference_answer: "Binary search runs in O(log n) time by repeatedly halving the array.",
        scenario: "technical", slice_name: "algorithms", severity: "medium",
        required_json_fields: [], rubric: [],
      },
      {
        prompt: "What is the difference between SQL JOIN and UNION?",
        expected_keyword: "columns",
        candidate_output: "JOIN combines columns from multiple tables based on a related column. UNION combines rows from multiple SELECT queries with the same number of columns.",
        reference_answer: "JOIN merges columns from different tables using a shared key. UNION stacks rows from multiple queries that share the same column structure.",
        scenario: "technical", slice_name: "databases", severity: "medium",
        required_json_fields: [], rubric: [],
      },
    ],
  },
};

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const scenarioKey = (body.scenario as string) || "general";
  const scenario = SCENARIOS[scenarioKey] ?? SCENARIOS.general;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  try {
    // Ensure dataset exists (409 = already exists, that's ok)
    await fetch(`${BASE}/api/v1/datasets`, {
      method: "POST", headers,
      body: JSON.stringify({ name: scenario.dataset, description: `Demo dataset for ${scenarioKey} scenario`, owner: "demo" }),
    });

    // Register experiment record — required for leaderboard to show it (409 = already exists, ok)
    await fetch(`${BASE}/api/v1/experiments`, {
      method: "POST", headers,
      body: JSON.stringify({
        name: scenario.experiment,
        dataset_name: scenario.dataset,
        owner: "demo",
        status: "active",
        description: `Demo experiment: ${scenario.experiment}`,
      }),
    });

    const evalRes = await fetch(`${BASE}/api/v1/evals`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        dataset_name: scenario.dataset,
        experiment_name: scenario.experiment,
        model_name: "heuristic-demo",
        prompt_version: "demo-v2",
        evaluator_profile: "balanced",
        samples: scenario.samples,
      }),
    });

    const text = await evalRes.text();
    let data: unknown;
    try { data = JSON.parse(text); } catch { data = { error: text || "upstream error" }; }

    if (!evalRes.ok) {
      const detail =
        (data as { detail?: string })?.detail ??
        (data as { error?: string })?.error ??
        `API returned ${evalRes.status}`;
      return NextResponse.json({ error: detail }, { status: evalRes.status });
    }

    // Create a release gate — must await before responding (serverless kills fire-and-forget)
    const gateCtrl = new AbortController();
    const gateTimer = setTimeout(() => gateCtrl.abort(), 4000);
    await fetch(`${BASE}/api/v1/release-gates`, {
      method: "POST",
      headers,
      signal: gateCtrl.signal,
      body: JSON.stringify({
        experiment_name: scenario.experiment,
        dataset_name: scenario.dataset,
        min_score: 0.70,
        evaluator_profile: "balanced",
      }),
    }).catch(() => {/* gate may already exist — ok */}).finally(() => clearTimeout(gateTimer));

    return NextResponse.json(data, { status: 200 });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Network error reaching API";
    return NextResponse.json({ error: msg }, { status: 503 });
  }
}
