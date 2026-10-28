"use client";

import { useWorkflow, STAGES, type StageId } from "@/lib/session";

interface ResearchFallback2DProps {
  onSelectNode: (id: string) => void;
  selectedNodeId: string;
}

export function ResearchFallback2D({
  onSelectNode,
  selectedNodeId,
}: ResearchFallback2DProps) {
  const { state, busy } = useWorkflow();

  const total = STAGES.length;
  const radius = 170;
  const cx = 220;
  const cy = 220;

  // Compute node coordinates around center
  const nodePositions = STAGES.map((stage, idx) => {
    const angle = (idx / total) * 2 * Math.PI - Math.PI / 2;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    return {
      ...stage,
      x,
      y,
      status: state.stages[stage.id].status,
    };
  });

  return (
    <div className="fallback-2d-container">
      <div className="fallback-header">
        <span className="badge-2d">2D GRAPH TOPOLOGY</span>
        <span className="caption-2d">Interactive workflow state diagram</span>
      </div>

      <svg
        className="graph-2d-svg"
        viewBox="0 0 440 440"
        role="region"
        aria-label="2D Research Workflow Diagram"
      >
        <defs>
          <radialGradient id="coreGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#00f0ff" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#0369a1" stopOpacity="0.4" />
          </radialGradient>
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Orbit loop */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth="1.5"
          strokeDasharray="4 4"
        />

        {/* Radial spokes */}
        {nodePositions.map((node) => {
          const isDone = node.status === "done";
          const isRunning = node.status === "running";
          const isError = node.status === "error";

          const strokeColor = isError
            ? "#f85149"
            : isRunning
            ? "#00f0ff"
            : isDone
            ? "#0284c7"
            : "#1e293b";

          return (
            <line
              key={`spoke-${node.id}`}
              x1={cx}
              y1={cy}
              x2={node.x}
              y2={node.y}
              stroke={strokeColor}
              strokeWidth={isRunning ? 2.5 : isDone ? 1.5 : 1}
              strokeOpacity={isRunning ? 0.9 : isDone ? 0.6 : 0.25}
            />
          );
        })}

        {/* Center Core Node */}
        <g
          className={`node-2d-group core ${selectedNodeId === "core" ? "selected" : ""}`}
          onClick={() => onSelectNode("core")}
          tabIndex={0}
          role="button"
          aria-label="Select Central Research Core"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") onSelectNode("core");
          }}
        >
          <circle
            cx={cx}
            cy={cy}
            r="44"
            fill="url(#coreGrad)"
            stroke={selectedNodeId === "core" ? "#00f0ff" : "#0284c7"}
            strokeWidth={selectedNodeId === "core" ? "3" : "1.5"}
            filter={busy ? "url(#glow)" : undefined}
          />
          <text
            x={cx}
            y={cy - 6}
            textAnchor="middle"
            fill="#ffffff"
            fontSize="10"
            fontWeight="700"
            letterSpacing="0.06em"
          >
            RESEARCH CORE
          </text>
          <text
            x={cx}
            y={cy + 12}
            textAnchor="middle"
            fill="rgba(255,255,255,0.75)"
            fontSize="9"
          >
            {busy ? "Running..." : "Click to view"}
          </text>
        </g>

        {/* Outer Stage Nodes */}
        {nodePositions.map((node, i) => {
          const isSelected = selectedNodeId === node.id;
          const status = node.status;
          const isRunning = status === "running";
          const isDone = status === "done";
          const isError = status === "error";

          let fillColor = "#1e293b";
          let strokeColor = "#334155";
          let textColor = "#94a3b8";

          if (isError) {
            fillColor = "rgba(248, 81, 73, 0.25)";
            strokeColor = "#f85149";
            textColor = "#f85149";
          } else if (isRunning) {
            fillColor = "rgba(0, 240, 255, 0.25)";
            strokeColor = "#00f0ff";
            textColor = "#00f0ff";
          } else if (isDone) {
            fillColor = "rgba(16, 185, 129, 0.2)";
            strokeColor = "#10b981";
            textColor = "#e2e8f0";
          }

          if (isSelected) {
            strokeColor = "#00f0ff";
          }

          return (
            <g
              key={node.id}
              className={`node-2d-group stage ${isSelected ? "selected" : ""} ${status}`}
              onClick={() => onSelectNode(node.id)}
              tabIndex={0}
              role="button"
              aria-label={`Select stage ${node.label}`}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") onSelectNode(node.id);
              }}
            >
              {isSelected && (
                <circle
                  cx={node.x}
                  cy={node.y}
                  r="28"
                  fill="none"
                  stroke="#00f0ff"
                  strokeWidth="1.5"
                  strokeDasharray="3 3"
                />
              )}
              <circle
                cx={node.x}
                cy={node.y}
                r="22"
                fill={fillColor}
                stroke={strokeColor}
                strokeWidth={isSelected ? "2.5" : "1.5"}
              />
              <text
                x={node.x}
                y={node.y - 2}
                textAnchor="middle"
                fill={textColor}
                fontSize="9"
                fontWeight="600"
              >
                {node.label}
              </text>
              <text
                x={node.x}
                y={node.y + 9}
                textAnchor="middle"
                fill="var(--text-faint)"
                fontSize="7.5"
                fontFamily="var(--mono)"
              >
                {isDone ? "DONE" : isRunning ? "RUNNING" : isError ? "ERR" : `0${i + 1}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
