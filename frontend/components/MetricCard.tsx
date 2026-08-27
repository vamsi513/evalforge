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
      borderRadius: 12, padding: "20px 24px",
      display: "flex", flexDirection: "column", gap: 14,
      position: "relative", overflow: "hidden",
    }}>
      {/* Subtle top accent line */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 2,
        background: `linear-gradient(90deg, ${color}, transparent)`,
        opacity: 0.5,
      }} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{
          fontSize: 11.5, color: "var(--muted)", fontWeight: 600,
          letterSpacing: "0.06em", textTransform: "uppercase",
        }}>
          {label}
        </span>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: `${color}20`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon size={15} style={{ color }} />
        </div>
      </div>

      <div>
        <span style={{
          fontSize: 30, fontWeight: 700, letterSpacing: "-1.5px",
          color: "var(--text)", fontVariantNumeric: "tabular-nums",
        }}>
          {value}
        </span>
        {sub && (
          <p style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 4 }}>{sub}</p>
        )}
      </div>
    </div>
  );
}
