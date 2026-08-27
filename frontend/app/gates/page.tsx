import { api } from "@/lib/api";
import { Shield, CheckCircle, XCircle } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function GatesPage() {
  const gates = await api.releaseGates().catch(() => []);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Release Gates</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Automated checks that block bad model updates from reaching production
        </p>
      </div>

      {gates.length === 0 ? (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 48, textAlign: "center" }}>
          <Shield size={32} style={{ color: "var(--muted)", margin: "0 auto 12px" }} />
          <p style={{ color: "var(--muted)", fontSize: 14 }}>No release gates configured yet.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {gates.map((g: Record<string, unknown>, i: number) => {
            const passed = g.status === "passed";
            return (
              <div key={i} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: "16px 20px", display: "flex", alignItems: "center", gap: 16 }}>
                {passed
                  ? <CheckCircle size={20} style={{ color: "var(--green)", flexShrink: 0 }} />
                  : <XCircle size={20} style={{ color: "var(--red)", flexShrink: 0 }} />}
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{String(g.experiment_name || "—")}</div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>Dataset: {String(g.dataset_name || "—")}</div>
                </div>
                <span style={{
                  fontSize: 12, fontWeight: 700, padding: "3px 10px", borderRadius: 6,
                  background: passed ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
                  color: passed ? "var(--green)" : "var(--red)",
                }}>
                  {passed ? "PASSED" : "FAILED"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
