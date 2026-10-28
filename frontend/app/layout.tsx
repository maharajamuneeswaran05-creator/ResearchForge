import type { Metadata } from "next";
import Link from "next/link";

import { WorkflowProvider } from "@/lib/session";
import "./globals.css";

export const metadata: Metadata = {
  title: "ResearchForge — autonomous research workflow",
  description:
    "Turn a research question into evidence, a research gap, an experiment, results, a critique and a final report.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <WorkflowProvider>
          <div className="app-shell">
            <header className="topbar">
              <Link href="/" className="brand">
                <span className="brand-mark">R</span>
                ResearchForge
                <span className="brand-sub">Autonomous research workflow</span>
              </Link>
              <nav className="btn-row">
                <Link className="btn ghost sm" href="/workspace">
                  Open workspace
                </Link>
              </nav>
            </header>
            <main className="page">{children}</main>
          </div>
        </WorkflowProvider>
      </body>
    </html>
  );
}
