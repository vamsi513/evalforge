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
    <div
      className="hover-card"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        padding: "20px 22px 18px",
        display: "flex",
        flexDirection: "column",
        gap: 0,
        position: "relative",
        overflow: "hidden",
        cursor: "default",
      }}
    >
      {/* Top gradient line */}
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 1,
        background: `linear-gradient(90deg, ${color}60, transparent 60%)`,
      }} />

      {/* Subtle glow in corner */}
      <div style={{
        position: "absolute", top: -30, right: -20, width: 80, height: 80,
        borderRadius: "50%", background: color, opacity: 0.04, filter: "blur(20px)",
        pointerEvents: "none",
      }} />

      {/* Label row */}
      <div style={{
        display: "flex", alignItems: "center",
        justifyContent: "space-between", marginBottom: 16,
      }}>
        <span style={{
          fontSize: 11, fontWeight: 600, color: "var(--subtle)",
          letterSpacing: "0.07em", textTransform: "uppercase",
        }}>
          {label}
        </span>
        <div style={{
          width: 30, height: 30, borderRadius: 8,
          background: `${color}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
          border: `1px solid ${color}25`,
        }}>
          <Icon size={14} style={{ color }} />
        </div>
      </div>

      {/* Value */}
      <div className="mono" style={{
        fontSize: 32, fontWeight: 700,
        letterSpacing: "-1.5px", color: "var(--text)",
        lineHeight: 1,
        marginBottom: 8,
      }}>
        {value}
      </div>

      {/* Sub label */}
      {sub && (
        <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{sub}</div>
      )}
    </div>
  );
}
