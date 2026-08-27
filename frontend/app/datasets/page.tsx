import { api } from "@/lib/api";
import { Database } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function DatasetsPage() {
  const datasets = await api.datasets().catch(() => []);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Datasets</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Collections of test cases used for regression evaluation
        </p>
      </div>

      {datasets.length === 0 ? (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 48, textAlign: "center" }}>
          <Database size={32} style={{ color: "var(--muted)", margin: "0 auto 12px" }} />
          <p style={{ color: "var(--muted)", fontSize: 14 }}>No datasets yet. Create one via the API.</p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
          {datasets.map((d) => (
            <div key={d.name} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <div style={{ width: 34, height: 34, borderRadius: 8, background: "var(--accent-dim)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Database size={16} style={{ color: "var(--accent)" }} />
                </div>
                <span style={{ fontWeight: 600, fontSize: 14 }}>{d.name}</span>
              </div>
              <div style={{ display: "flex", gap: 20, fontSize: 12.5, color: "var(--muted)" }}>
                <span><b style={{ color: "var(--text)" }}>{d.case_count ?? "—"}</b> cases</span>
                <span>Created {new Date(d.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
