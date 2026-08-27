"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FlaskConical, Database, GitCompare, Shield, Zap } from "lucide-react";

const nav = [
  { href: "/",            label: "Overview",      icon: LayoutDashboard },
  { href: "/runs",        label: "Eval Runs",     icon: FlaskConical },
  { href: "/datasets",    label: "Datasets",      icon: Database },
  { href: "/experiments", label: "Experiments",   icon: GitCompare },
  { href: "/gates",       label: "Release Gates", icon: Shield },
];

export default function Sidebar() {
  const path = usePathname();

  return (
    <aside style={{
      width: 224, flexShrink: 0,
      background: "var(--surface)",
      borderRight: "1px solid var(--border)",
      display: "flex", flexDirection: "column",
      height: "100vh", overflow: "hidden",
    }}>
      {/* Logo */}
      <div style={{
        padding: "20px 18px 18px",
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8, flexShrink: 0,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 12px rgba(99,102,241,0.4)",
          }}>
            <Zap size={15} color="#fff" fill="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14.5, letterSpacing: "-0.3px", color: "var(--text)" }}>
              EvalForge
            </div>
            <div style={{ fontSize: 10.5, color: "var(--subtle)", letterSpacing: "0.02em" }}>
              LLM Quality Platform
            </div>
          </div>
        </div>
      </div>

      {/* Section label */}
      <div style={{ padding: "16px 18px 6px" }}>
        <span style={{ fontSize: 10.5, fontWeight: 600, color: "var(--subtle)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Workspace
        </span>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "0 10px", display: "flex", flexDirection: "column", gap: 2 }}>
        {nav.map(({ href, label, icon: Icon }) => {
          const active = path === href;
          return (
            <Link
              key={href}
              href={href}
              className={`nav-item${active ? " nav-active" : ""}`}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 10px", borderRadius: 8,
                fontSize: 13.5, fontWeight: active ? 600 : 400,
                color: active ? "var(--text)" : "var(--muted)",
                background: active ? "var(--surface2)" : "transparent",
                position: "relative",
                borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
                paddingLeft: active ? 9 : 10,
              }}
            >
              <Icon
                size={15}
                style={{ color: active ? "var(--accent)" : "var(--muted)", flexShrink: 0 }}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div style={{
        padding: "14px 18px",
        borderTop: "1px solid var(--border)",
      }}>
        <div style={{ fontSize: 11.5, color: "var(--muted)", fontWeight: 500 }}>
          Vamsi Krishna Sadu
        </div>
        <div style={{ fontSize: 10.5, color: "var(--subtle)", marginTop: 2 }}>
          v2.0 · Production
        </div>
      </div>
    </aside>
  );
}
