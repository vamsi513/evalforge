"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FlaskConical, Database, GitCompare, Shield, Activity } from "lucide-react";
import clsx from "clsx";

const nav = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/runs", label: "Eval Runs", icon: FlaskConical },
  { href: "/datasets", label: "Datasets", icon: Database },
  { href: "/experiments", label: "Experiments", icon: GitCompare },
  { href: "/gates", label: "Release Gates", icon: Shield },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside style={{ width: 220, background: "var(--surface)", borderRight: "1px solid var(--border)", flexShrink: 0 }}
      className="flex flex-col h-screen">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5" style={{ borderBottom: "1px solid var(--border)" }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Activity size={15} color="#fff" />
        </div>
        <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: "-0.3px", color: "var(--text)" }}>EvalForge</span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 p-3 flex-1">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = path === href;
          return (
            <Link key={href} href={href}
              style={{
                display: "flex", alignItems: "center", gap: 10, padding: "8px 12px",
                borderRadius: 8, fontSize: 13.5, fontWeight: active ? 600 : 400,
                color: active ? "var(--text)" : "var(--muted)",
                background: active ? "var(--surface2)" : "transparent",
                textDecoration: "none", transition: "all 0.15s",
              }}>
              <Icon size={15} style={{ color: active ? "var(--accent)" : "var(--muted)" }} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4" style={{ borderTop: "1px solid var(--border)", fontSize: 11, color: "var(--muted)" }}>
        Built by Vamsi Krishna Sadu
      </div>
    </aside>
  );
}
