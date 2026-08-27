import { api } from "@/lib/api";
import { Database, Layers, FlaskConical } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function DatasetsPage() {
  const [datasets, runs] = await Promise.all([
    api.datasets().catch(() => []),
    api.runs().catch(() => []),
  ]);

  // API doesn't populate case_count — derive it from eval run results
  const runsByDataset = runs.reduce<Record<string, { count: number; runs: number }>>((acc, r) => {
    const key = r.dataset_name;
    if (!acc[key]) acc[key] = { count: 0, runs: 0 };
    acc[key].count += r.results?.length ?? 0;
    acc[key].runs += 1;
    return acc;
  }, {});

  const getCount = (name: string) =>
    runsByDataset[name]?.count ?? 0;

  const totalCases = datasets.reduce((s, d) => s + getCount(d.name), 0);
  const totalRuns = datasets.reduce((s, d) => s + (runsByDataset[d.name]?.runs ?? 0), 0);

  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.7px", marginBottom: 5 }}>Datasets</h1>
          <p style={{ fontSize: 13.5, color: "var(--muted)" }}>
            Collections of test cases used for regression evaluation
          </p>
        </div>
        {datasets.length > 0 && (
          <div style={{
            fontSize: 12.5, color: "var(--muted)",
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 8, padding: "6px 16px", display: "flex", gap: 16,
          }}>
            <span>
              <span className="mono" style={{ color: "var(--text)", fontWeight: 600 }}>{datasets.length}</span>
              {" datasets"}
            </span>
            <span style={{ color: "var(--border2)" }}>·</span>
            <span>
              <span className="mono" style={{ color: "var(--text)", fontWeight: 600 }}>{totalCases}</span>
              {" cases evaluated"}
            </span>
            <span style={{ color: "var(--border2)" }}>·</span>
            <span>
              <span className="mono" style={{ color: "var(--text)", fontWeight: 600 }}>{totalRuns}</span>
              {" runs"}
            </span>
          </div>
        )}
      </div>

      {datasets.length === 0 ? (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 14, padding: "60px 48px", textAlign: "center",
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: "var(--accent-dim)", border: "1px solid rgba(99,102,241,0.2)",
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 16px",
          }}>
            <Database size={22} style={{ color: "var(--accent)" }} />
          </div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>No datasets yet</div>
          <p style={{ fontSize: 13, color: "var(--muted)", maxWidth: 380, margin: "0 auto 20px" }}>
            Datasets are created automatically when you run the demo eval. You can also create them via the API.
          </p>
          <pre style={{ display: "inline-block", textAlign: "left", fontSize: 12 }}>{`POST /api/v1/datasets
{ "name": "my-dataset", "owner": "team" }`}</pre>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
          {datasets.map((d) => {
            const caseCount = getCount(d.name);
            const runCount = runsByDataset[d.name]?.runs ?? 0;
            return (
              <div
                key={d.name}
                className="hover-card"
                style={{
                  background: "var(--surface)", border: "1px solid var(--border)",
                  borderRadius: 14, padding: 20,
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 16 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 9, flexShrink: 0,
                    background: "var(--accent-dim)", border: "1px solid rgba(99,102,241,0.2)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <Database size={16} style={{ color: "var(--accent)" }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontWeight: 600, fontSize: 13.5, marginBottom: 2,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {d.name}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      Created {new Date(d.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <div style={{
                    flex: 1, display: "flex", alignItems: "center", gap: 6,
                    padding: "8px 12px", borderRadius: 8, background: "var(--bg)",
                    border: "1px solid var(--border)",
                  }}>
                    <Layers size={12} style={{ color: "var(--muted)" }} />
                    <span className="mono" style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>
                      {caseCount}
                    </span>
                    <span style={{ fontSize: 11.5, color: "var(--muted)" }}>cases</span>
                  </div>
                  <div style={{
                    flex: 1, display: "flex", alignItems: "center", gap: 6,
                    padding: "8px 12px", borderRadius: 8, background: "var(--bg)",
                    border: "1px solid var(--border)",
                  }}>
                    <FlaskConical size={12} style={{ color: "var(--muted)" }} />
                    <span className="mono" style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>
                      {runCount}
                    </span>
                    <span style={{ fontSize: 11.5, color: "var(--muted)" }}>runs</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
