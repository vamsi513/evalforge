import { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string;
  sub?: string;
  icon: LucideIcon;
  color?: string;
}

export default function MetricCard({ label, value, sub, icon: Icon, color = "var(--accent)" }: Props) {
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 12, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 12.5, color: "var(--muted)", fontWeight: 500, letterSpacing: "0.02em" }}>
          {label.toUpperCase()}
        </span>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: `${color}22`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Icon size={15} style={{ color }} />
        </div>
      </div>
      <div>
        <span style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-1px", color: "var(--text)" }}>{value}</span>
        {sub && <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>{sub}</p>}
      </div>
    </div>
  );
}
