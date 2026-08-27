"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FlaskConical, Database, GitCompare, Shield, Zap, X, Menu } from "lucide-react";

const nav = [
  { href: "/",            label: "Overview",      icon: LayoutDashboard },
  { href: "/runs",        label: "Eval Runs",     icon: FlaskConical },
  { href: "/datasets",    label: "Datasets",      icon: Database },
  { href: "/experiments", label: "Experiments",   icon: GitCompare },
  { href: "/gates",       label: "Release Gates", icon: Shield },
];

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const path = usePathname();

  // Close on route change
  useEffect(() => { setOpen(false); }, [path]);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  // Prevent body scroll when open
  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  return (
    <>
      {/* Top bar (mobile only) */}
      <header className="mobile-header" style={{
        display: "none",
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 100,
        height: 52, background: "var(--surface)", borderBottom: "1px solid var(--border)",
        alignItems: "center", justifyContent: "space-between",
        padding: "0 16px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 26, height: 26, borderRadius: 7, flexShrink: 0,
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 10px rgba(99,102,241,0.35)",
          }}>
            <Zap size={13} color="#fff" fill="#fff" />
          </div>
          <span style={{ fontWeight: 700, fontSize: 14, letterSpacing: "-0.3px" }}>EvalForge</span>
        </div>
        <button
          onClick={() => setOpen(o => !o)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          style={{
            background: "none", border: "none", cursor: "pointer",
            color: "var(--text)", padding: 4, display: "flex",
          }}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Backdrop */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{
            display: "none",
            position: "fixed", inset: 0, zIndex: 101,
            background: "rgba(0,0,0,0.6)", backdropFilter: "blur(2px)",
          }}
          className="mobile-backdrop"
        />
      )}

      {/* Slide-in drawer */}
      <nav
        className="mobile-drawer"
        aria-label="Mobile navigation"
        style={{
          display: "none",
          position: "fixed", top: 0, left: 0, bottom: 0, zIndex: 102,
          width: 240, background: "var(--surface)", borderRight: "1px solid var(--border)",
          flexDirection: "column",
          transform: open ? "translateX(0)" : "translateX(-100%)",
          transition: "transform 0.22s ease",
          overflowY: "auto",
        }}
      >
        <div style={{
          padding: "16px 18px", borderBottom: "1px solid var(--border)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <div style={{
              width: 26, height: 26, borderRadius: 7,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Zap size={13} color="#fff" fill="#fff" />
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: 13.5, letterSpacing: "-0.3px" }}>EvalForge</div>
              <div style={{ fontSize: 10, color: "var(--subtle)" }}>LLM Evaluation Platform</div>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close navigation menu"
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 4 }}
          >
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: "12px 10px", flex: 1 }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: "var(--subtle)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "4px 10px 8px" }}>
            Workspace
          </div>
          {nav.map(({ href, label, icon: Icon }) => {
            const active = path === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`nav-item${active ? " nav-active" : ""}`}
                style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "9px 10px", borderRadius: 8, marginBottom: 2,
                  fontSize: 13.5, fontWeight: active ? 600 : 400,
                  color: active ? "var(--text)" : "var(--muted)",
                  background: active ? "var(--surface2)" : "transparent",
                  borderLeft: active ? "2px solid var(--accent)" : "2px solid transparent",
                  paddingLeft: active ? 9 : 10,
                }}
              >
                <Icon size={15} style={{ color: active ? "var(--accent)" : "var(--muted)", flexShrink: 0 }} />
                {label}
              </Link>
            );
          })}
        </div>

        <div style={{ padding: "12px 18px", borderTop: "1px solid var(--border)" }}>
          <div style={{ fontSize: 11.5, color: "var(--muted)", fontWeight: 500, marginBottom: 6 }}>
            Vamsi Krishna Sadu
          </div>
          <a
            href="https://github.com/vamsi513/evalforge"
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11.5, color: "var(--subtle)", textDecoration: "none" }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
            </svg>
            View source
          </a>
        </div>
      </nav>
    </>
  );
}
