# ResearchForge System Architecture

## 1. High-Level Architecture

ResearchForge operates as an end-to-end scientific research workspace that transforms natural-language scientific questions into verifiable, peer-reviewed computational research artifacts.

```
+-------------------------------------------------------------------------------+
|                             Next.js 16 Client                                 |
|  +---------------------+   +-----------------------+   +-------------------+  |
|  |     LeftSidebar     |   |   ResearchScene (3D)  |   | ResearchInspector |  |
|  | - Stage Navigation  |   | - React Three Fiber   |   | - Context panels  |  |
|  | - Session History   |   | - Dynamic WebGL       |   | - Code viewer     |  |
|  | - Provider Status   |   | - 2D Canvas Fallback  |   | - Report exporter |  |
|  +---------------------+   +-----------------------+   +-------------------+  |
+-------------------------------------------------------------------------------+
                                        | (HTTP /backend proxy)
                                        v
+-------------------------------------------------------------------------------+
|                             FastAPI Backend                                   |
|  +-------------------------------------------------------------------------+  |
|  | API Router: /api/research/...                                           |  |
|  +-------------------------------------------------------------------------+  |
|     |                      |                     |                   |        |
|     v                      v                     v                   v        |
|  TavilyClient        NebiusClient         ExperimentCode      ExecutionSvc    |
|  - Search query      - Nemotron 30B/340B  - AST Security      - Nebius Jobs   |
|  - Deduplication     - Structured JSON    - Seed enforcement  - Demo sandbox  |
|  - URL normalize     - Reasoning parsing  - Metric logging    - Telemetry     |
+-------------------------------------------------------------------------------+
       |                      |                                        |
       v                      v                                        v
  [Tavily API]       [NVIDIA NIM / Nebius]                [Nebius Serverless / S3]
```

---

## 2. Pipeline Sequence

1. **Evidence Collection (`POST /api/research/evidence`)**:
   - Accepts `research_question` and `max_results`.
   - Calls Tavily API to fetch current scientific literature.
   - Normalizes URLs, deduplicates sources, and preserves all attribution.
2. **Research Gap Synthesis (`POST /api/research/gap`)**:
   - Prompts NVIDIA Nemotron with collected snippets.
   - Compiles established findings, conflicts, limitations, and potential research gaps.
   - Generates confidence rating (high/medium/low) with quantitative reliability score (0.0 to 1.0).
3. **Hypothesis & Planning (`POST /api/research/experiment-plan`)**:
   - Converts research gaps into a formal testable hypothesis.
   - Defines independent, dependent, and control variables.
   - Mandates a concrete baseline comparison method.
4. **Code Generation (`POST /api/research/experiment-code`)**:
   - Emits a standalone Python script with `RANDOM_SEED = 42`.
   - Passes through the **AST Static Security Analyzer** to ensure no network calls or host compromise attempts.
   - Emits standard `METRIC <key>=<value>` telemetry lines on stdout.
5. **Execution & Metrics (`POST /api/research/experiment-execute`)**:
   - Submits a job to Nebius Serverless AI (or executes in an isolated local sandbox when running in demo mode).
   - Captures stdout/stderr, execution time, and parses quantitative metrics.
6. **Adversarial Critique (`POST /api/research/critic`)**:
   - Evaluates the experiment as a skeptical peer reviewer.
   - Identifies threats to validity, confounders, and suggests follow-up runs.
7. **Structured Report (`POST /api/research/report`)**:
   - Compiles a 13-section structured paper.
   - Grounds numeric results strictly in experimental output.
   - Formats citations with clickable links.
8. **Export & Reproducibility Review**:
   - Exports formatted Markdown report.
   - Exports complete JSON Reproducibility Bundle including code, data, telemetry, and audit checklist.

---

## 3. Data Contracts

All data interchange between backend and frontend adheres to strict Pydantic schemas in `backend/app/schemas/research.py` and TypeScript interfaces in `frontend/lib/types.ts`.
