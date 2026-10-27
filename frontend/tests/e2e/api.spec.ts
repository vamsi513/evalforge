import { test, expect, scenarios } from "./fixtures";

/**
 * API tests against the backend directly (port 8101) using Playwright's
 * request fixture, so they exercise the FastAPI routes rather than the Next
 * proxy in front of them.
 *
 * The backend runs with JUDGE_PROVIDER=mock and the demo model name
 * "heuristic-demo", which routes to the in-process deterministic evaluators --
 * no LLM call, no API key, and a real zero for cost.
 */
const { api } = scenarios;

test.describe("API", () => {
  test("GET /api/v1/evals returns a list of runs with the documented shape", async ({ request }) => {
    const res = await request.get("/api/v1/evals");
    expect(res.status()).toBe(200);

    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);

    // Shape is only asserted when a run exists; this test does not create one,
    // so it must not assume the ordering of the suite.
    if (body.length > 0) {
      const run = body[0];
      expect(run).toHaveProperty("id");
      expect(run).toHaveProperty("dataset_name");
      expect(run).toHaveProperty("model_name");
      expect(typeof run.average_score).toBe("number");
      expect(Array.isArray(run.results)).toBe(true);
    }
  });

  test("POST /api/v1/evals scores samples and returns a run", async ({ request }) => {
    // The dataset may already exist from an earlier run; 201 and 409 are both
    // fine here, and neither is what this test is about.
    const created = await request.post("/api/v1/datasets", { data: api.validDataset });
    expect([201, 409]).toContain(created.status());

    const res = await request.post("/api/v1/evals", { data: api.validEval });
    expect(res.status()).toBe(201);

    const run = await res.json();
    expect(run.dataset_name).toBe(api.validEval.dataset_name);
    expect(run.model_name).toBe(api.validEval.model_name);
    expect(typeof run.average_score).toBe("number");
    expect(run.average_score).toBeGreaterThan(0);
    expect(run.results).toHaveLength(api.validEval.samples.length);

    const [first] = run.results;
    expect(typeof first.score).toBe("number");
    expect(typeof first.passed).toBe("boolean");
    // The heuristic path makes no provider call, so the cost is a real zero
    // rather than an estimate.
    expect(first.cost_usd).toBe(0);
  });

  test("POST /api/v1/datasets rejects a description under the minimum length", async ({ request }) => {
    // DatasetCreate.description is Field(min_length=10); this payload sends 4
    // characters, so the request fails validation before touching the database.
    const res = await request.post("/api/v1/datasets", {
      data: api.datasetWithShortDescription,
    });
    expect(res.status()).toBe(422);

    const body = await res.json();
    expect(Array.isArray(body.detail)).toBe(true);
    const descriptionError = body.detail.find((d: { loc: string[] }) =>
      d.loc.includes("description"),
    );
    expect(descriptionError).toBeTruthy();
  });

  test("GET /api/v1/evals/jobs/<unknown id> returns 404", async ({ request }) => {
    const res = await request.get(`/api/v1/evals/jobs/${api.missingJobId}`);
    expect(res.status()).toBe(404);

    const body = await res.json();
    expect(body).toHaveProperty("detail");
  });
});
