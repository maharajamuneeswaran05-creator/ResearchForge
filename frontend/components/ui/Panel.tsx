import type { ReactNode } from "react";

import type { StageStatus } from "@/lib/session";
import { StatusPill } from "./StatusPill";

interface PanelProps {
  step: number;
  title: string;
  caption?: string;
  status: StageStatus;
  error?: string;
  action?: ReactNode;
  tight?: boolean;
  children: ReactNode;
}

export function Panel({
  step,
  title,
  caption,
  status,
  error,
  action,
  tight,
  children,
}: PanelProps) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div className="panel-title">
          <span className="step">{String(step).padStart(2, "0")}</span>
          <h2>{title}</h2>
          {caption ? <span className="panel-caption">{caption}</span> : null}
        </div>
        <div className="btn-row">
          {action}
          <StatusPill status={status} />
        </div>
      </header>
      {error ? (
        <div style={{ padding: "14px 18px 0" }}>
          <div className="error-box">
            <strong>Stage failed</strong>
            {error}
          </div>
        </div>
      ) : null}
      <div className={`panel-body${tight ? " tight" : ""}`}>{children}</div>
    </section>
  );
}
