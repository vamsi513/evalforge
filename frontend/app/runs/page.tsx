import { api } from "@/lib/api";
import RunsTable from "@/components/RunsTable";

export const revalidate = 30;

export default async function RunsPage() {
  const runs = await api.runs().catch(() => []);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Eval Runs</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Every batch of AI outputs scored against your datasets
        </p>
      </div>

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <span style={{ fontSize: 13.5, fontWeight: 600 }}>{runs.length} total runs</span>
        </div>
        <RunsTable runs={runs} />
      </div>
    </div>
  );
}
