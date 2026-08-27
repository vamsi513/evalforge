import { api } from "@/lib/api";
import { Database, Layers } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function DatasetsPage() {
  const datasets = await api.datasets().catch(() => []);

  const totalCases = datasets.reduce((s, d) => s + (d.case_count ?? 0), 0);

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
            borderRadius: 8, padding: "6px 14px",
          }}>
            <span className="mono" style={{ color: "var(--text)", fontWeight: 600 }}>{datasets.length}</span>
            {" datasets · "}
            <span className="mono" style={{ color: "var(--text)", fontWeight: 600 }}>{totalCases}</span>
            {" total cases"}
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
          {datasets.map((d) => (
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
                  <div style={{ fontWeight: 600, fontSize: 13.5, marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {d.name}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    {new Date(d.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  </div>
                </div>
              </div>

              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 12px", borderRadius: 8, background: "var(--bg)",
                border: "1px solid var(--border)",
              }}>
                <Layers size={13} style={{ color: "var(--muted)" }} />
                <span className="mono" style={{ fontWeight: 600, fontSize: 13, color: "var(--text)" }}>
                  {d.case_count ?? "—"}
                </span>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>test cases</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
