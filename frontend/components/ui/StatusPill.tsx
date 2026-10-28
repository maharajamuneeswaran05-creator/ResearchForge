import type { StageStatus } from "@/lib/session";

const LABELS: Record<StageStatus, string> = {
  idle: "Pending",
  running: "Running",
  done: "Complete",
  error: "Failed",
};

export function StatusPill({
  status,
  label,
}: {
  status: StageStatus;
  label?: string;
}) {
  return (
    <span className={`pill ${status}`}>
      <span className="dot" />
      {label ?? LABELS[status]}
    </span>
  );
}
