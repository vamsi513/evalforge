import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import { Analytics } from "@vercel/analytics/next";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const DESCRIPTION =
  "Portfolio project: deterministic multi-signal LLM evaluation with heuristic evaluators, OpenAI/Anthropic/Mistral judge adapters, experiment tracking, and release gates. Built with FastAPI, Next.js, and SQLAlchemy.";

export const metadata: Metadata = {
  metadataBase: new URL("https://evalforge-platform.vercel.app"),
  title: "EvalForge — LLM Evaluation Platform",
  description: DESCRIPTION,
  openGraph: {
    title: "EvalForge — LLM Evaluation Platform",
    description: DESCRIPTION,
    url: "https://evalforge-platform.vercel.app",
    siteName: "EvalForge",
    type: "website",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "EvalForge — LLM Evaluation Platform",
    description: DESCRIPTION,
    creator: "@vamsi513",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0a0a0f",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body style={{ background: "var(--bg)", display: "flex", height: "100vh", overflow: "hidden" }}>
        <a href="#main-content" className="skip-nav">
          Skip to main content
        </a>
        <Sidebar />
        <MobileNav />
        <main id="main-content" className="app-main" style={{ flex: 1, overflowY: "auto" }}>
          {children}
        </main>
        <Analytics />
      </body>
    </html>
  );
}
