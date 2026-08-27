"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Zap } from "lucide-react";

export default function SeedButton() {
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [msg, setMsg] = useState("");
  const router = useRouter();

  async function seed() {
    setState("running");
    setMsg("");
    try {
      const res = await fetch("/api/seed", { method: "POST" });
      const data = await res.json() as { seeded?: { name: string; steps: Record<string, string> }[] };
      if (res.ok || res.status === 207) {
        const ok = data.seeded?.filter(s =>
          Object.values(s.steps).every(v => v === "ok" || v === "skipped")
        ).length ?? 0;
        setMsg(`Seeded ${ok} of 3 experiment${ok !== 1 ? "s" : ""}`);
        setState("done");
        router.refresh();
      } else {
        setMsg("Seed failed — API may be unreachable");
        setState("error");
      }
    } catch {
      setMsg("Network error");
      setState("error");
    }
  }

  return (
    <div style={{ marginTop: 20 }}>
      <button
        onClick={seed}
        disabled={state === "running" || state === "done"}
        style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "9px 20px", borderRadius: 8, border: "1px solid rgba(99,102,241,0.4)",
          background: state === "done" ? "var(--green-dim)" : "var(--accent-dim)",
          color: state === "done" ? "var(--green)" : "var(--accent)",
          cursor: state === "running" || state === "done" ? "not-allowed" : "pointer",
          fontSize: 13, fontWeight: 600, fontFamily: "inherit",
          opacity: state === "running" ? 0.6 : 1, transition: "opacity 0.15s",
        }}
      >
        {state === "running" ? (
          <>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
              style={{ animation: "spin 1s linear infinite" }}>
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
            Seeding all 3 experiments…
          </>
        ) : state === "done" ? (
          <>{msg}</>
        ) : (
          <>
            <Zap size={13} />
            Load demo data
          </>
        )}
      </button>
      {state === "error" && (
        <p style={{ marginTop: 8, fontSize: 12, color: "var(--red)" }}>{msg}</p>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
