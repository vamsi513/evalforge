import { NextResponse } from "next/server";

const BASE = process.env.EVALFORGE_API_URL ?? "http://23.21.42.197:8001";
const KEY = process.env.EVALFORGE_API_KEY ?? "";

const SCENARIOS = [
  {
    dataset: "demo-general-knowledge",
    experiment: "General Knowledge",
    samples: [
      { prompt: "What is the capital of France?", expected_keyword: "Paris", candidate_output: "The capital of France is Paris, known for the Eiffel Tower.", reference_answer: "Paris is the capital and largest city of France.", scenario: "factual", slice_name: "geography", severity: "medium", required_json_fields: [], rubric: [] },
      { prompt: "What is 2 + 2?", expected_keyword: "4", candidate_output: "2 + 2 equals 4.", reference_answer: "The answer is 4.", scenario: "math", slice_name: "arithmetic", severity: "low", required_json_fields: [], rubric: [] },
      { prompt: "Who wrote Romeo and Juliet?", expected_keyword: "Shakespeare", candidate_output: "Romeo and Juliet was written by William Shakespeare.", reference_answer: "William Shakespeare wrote Romeo and Juliet.", scenario: "literature", slice_name: "authors", severity: "medium", required_json_fields: [], rubric: [] },
    ],
    minScore: 0.70,
  },
  {
    dataset: "demo-customer-support",
    experiment: "Customer Support",
    samples: [
      { prompt: "How do I request a refund for my order?", expected_keyword: "refund", candidate_output: "To request a refund, go to your order history, select the order, and click 'Request Refund'. Refunds are processed within 5-7 business days.", reference_answer: "Customers can request refunds through order history within 30 days of purchase. Processing takes 5-7 business days.", scenario: "support", slice_name: "refunds", severity: "high", required_json_fields: [], rubric: [] },
      { prompt: "What is your shipping policy for international orders?", expected_keyword: "shipping", candidate_output: "International shipping takes 10-21 business days. We ship to over 50 countries. Customs fees may apply.", reference_answer: "International orders ship via standard carrier in 10-21 business days to 50+ countries. Import duties and customs fees are the customer's responsibility.", scenario: "support", slice_name: "shipping", severity: "medium", required_json_fields: [], rubric: [] },
      { prompt: "My account is locked. How do I regain access?", expected_keyword: "password", candidate_output: "If your account is locked, use the 'Forgot Password' link on the login page to reset your password via email.", reference_answer: "Locked accounts can be unlocked by resetting the password through the 'Forgot Password' flow on the login page.", scenario: "support", slice_name: "account", severity: "high", required_json_fields: [], rubric: [] },
    ],
    minScore: 0.70,
  },
  {
    dataset: "demo-code-review",
    experiment: "Code & Tech",
    samples: [
      { prompt: "What does the 'async/await' pattern do in JavaScript?", expected_keyword: "asynchronous", candidate_output: "async/await is syntactic sugar for Promises that makes asynchronous code look synchronous, improving readability.", reference_answer: "async/await allows writing asynchronous code in a synchronous style using Promises under the hood.", scenario: "technical", slice_name: "javascript", severity: "medium", required_json_fields: [], rubric: [] },
      { prompt: "What is the time complexity of binary search?", expected_keyword: "O(log n)", candidate_output: "Binary search has a time complexity of O(log n) because it halves the search space with each step.", reference_answer: "Binary search runs in O(log n) time by repeatedly halving the array.", scenario: "technical", slice_name: "algorithms", severity: "medium", required_json_fields: [], rubric: [] },
      { prompt: "What is the difference between SQL JOIN and UNION?", expected_keyword: "columns", candidate_output: "JOIN combines columns from multiple tables based on a related column. UNION combines rows from multiple SELECT queries with the same number of columns.", reference_answer: "JOIN merges columns from different tables using a shared key. UNION stacks rows from multiple queries that share the same column structure.", scenario: "technical", slice_name: "databases", severity: "medium", required_json_fields: [], rubric: [] },
    ],
    minScore: 0.75,
  },
];

export async function POST() {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (KEY) headers["X-API-Key"] = KEY;

  const results: { experiment: string; status: string; error?: string }[] = [];

  for (const s of SCENARIOS) {
    try {
      // Ensure dataset exists
      await fetch(`${BASE}/api/v1/datasets`, {
        method: "POST", headers,
        body: JSON.stringify({ name: s.dataset, description: `Demo ${s.experiment}`, owner: "demo" }),
      });

      // Run eval
      const evalRes = await fetch(`${BASE}/api/v1/evals`, {
        method: "POST", headers,
        body: JSON.stringify({
          dataset_name: s.dataset,
          experiment_name: s.experiment,
          model_name: "heuristic-demo",
          prompt_version: "demo-v2",
          evaluator_profile: "balanced",
          samples: s.samples,
        }),
      });

      if (!evalRes.ok) {
        results.push({ experiment: s.experiment, status: "eval_failed", error: `${evalRes.status}` });
        continue;
      }

      // Create release gate
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 4000);
      await fetch(`${BASE}/api/v1/release-gates`, {
        method: "POST", headers, signal: ctrl.signal,
        body: JSON.stringify({
          experiment_name: s.experiment,
          dataset_name: s.dataset,
          min_score: s.minScore,
          evaluator_profile: "balanced",
        }),
      }).catch(() => {}).finally(() => clearTimeout(t));

      results.push({ experiment: s.experiment, status: "ok" });
    } catch (err) {
      results.push({ experiment: s.experiment, status: "error", error: err instanceof Error ? err.message : "unknown" });
    }
  }

  const allOk = results.every(r => r.status === "ok");
  return NextResponse.json({ seeded: results }, { status: allOk ? 200 : 207 });
}
