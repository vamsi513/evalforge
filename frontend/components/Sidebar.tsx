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
              LLM Evaluation Platform
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
        <div style={{ fontSize: 11.5, color: "var(--muted)", fontWeight: 500, marginBottom: 6 }}>
          Vamsi Krishna Sadu
        </div>
        <a
          href="https://github.com/vamsi513/evalforge"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 11.5, color: "var(--subtle)",
            textDecoration: "none", transition: "color 0.15s",
          }}
          onMouseEnter={e => (e.currentTarget.style.color = "var(--text)")}
          onMouseLeave={e => (e.currentTarget.style.color = "var(--subtle)")}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
          </svg>
          View source on GitHub
        </a>
      </div>
    </aside>
  );
}
