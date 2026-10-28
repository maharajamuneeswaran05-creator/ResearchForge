# ResearchForge Full-Stack Engineering Guidelines & Architecture

## Architecture Overview

ResearchForge is an autonomous scientific research workspace that accelerates the research lifecycle across 10 stages:
1. **Evidence Collection**: Literature search and URL deduplication via Tavily API.
2. **Research Gap Analysis**: Structured synthesis of findings, conflicts, limitations, and gaps via NVIDIA Nemotron.
3. **Hypothesis & Planning**: Falsifiable hypothesis design with independent/dependent/control variables and mandatory baselines.
4. **Experiment Code Generation**: Runnable Python scripts with dependencies, deterministic seeds (`RANDOM_SEED = 42`), and standard telemetry format (`METRIC key=value`).
5. **AST Security Audit**: Static syntax tree inspection forbidding process, network, and host environment escalation.
6. **Experiment Execution**: Serverless execution on Nebius AI Cloud (or isolated local sandbox in demo mode).
7. **Results & Metrics**: Quantitative telemetry parsing and empirical outcome grounding.
8. **Adversarial Critique**: Skeptical peer review evaluating threats to validity, confounders, and baseline rigor.
9. **Structured Report**: 13-section publishable report with preserved citations, numerical validation, and confidence scores.
10. **Reproducibility Review & Export**: Reproducibility checklist and one-click JSON/Markdown export bundle.

### Technology Stack
- **Backend**: FastAPI 0.142, Python 3.12+, Pydantic v2, HTTPX, Uvicorn.
- **Frontend**: Next.js 16 (App Router) with Turbopack, React 19, TypeScript 5.9.
- **3D Graphics**: Three.js (`three`), `@react-three/fiber`, `@react-three/drei`.
- **Styling**: Vanilla CSS design system with CSS custom properties, glassmorphism, responsive grid layouts.
- **State Management**: `WorkflowProvider` (React Context) in `frontend/lib/session.tsx` with session persistence.
- **Backend API**: FastAPI proxy via Next.js `/backend/[...path]` or direct CORS.

---

## Coding Rules & Conventions

1. **TypeScript Strictness**:
   - Maintain 100% type safety. No `any` casting where concrete interfaces exist.
   - Response contracts in `frontend/lib/types.ts` mirror backend Pydantic models in `backend/app/schemas/research.py`.

2. **React 19 & Next.js 16 Compatibility**:
   - Use client directives (`"use client"`) only on components needing browser APIs, hooks, or 3D WebGL contexts.
   - Keep 3D Canvas rendering isolated inside dynamic client-only imports (`ssr: false`) to avoid server-side hydration mismatches.
   - Isolate 3D WebGL rendering from HTML UI; keep accessibility controls, forms, and inspector panels in semantic HTML.

3. **3D Scene Architecture**:
   - Single main WebGL canvas. Do not instantiate multiple WebGL contexts.
   - Lightweight geometries (spheres, rings, instanced lines) and reused materials.
   - Avoid infinite heavy render loops when canvas is idle.
   - Respect `prefers-reduced-motion` media query and provide a clean 2D schematic fallback.
   - Ensure pointer interactions (raycasting) handle camera zooms and aspect ratio changes cleanly.

4. **Security & Secrets**:
   - Never expose API keys or backend secrets to browser code.
   - All backend calls route through the `/backend` same-origin proxy or configured `NEXT_PUBLIC_API_BASE_URL`.
   - Prevent XSS: do not use unescaped `dangerouslySetInnerHTML` for model outputs; render text safely.
   - Defensive headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.

5. **Data Integrity & Honesty**:
   - Never simulate or fake backend success states.
   - If an experiment fails or returns an error (e.g. Nebius unconfigured), display the exact error honestly.
   - Differentiate test/demo data with prominent `[DEMO DATA]` or `[DEMO MODE]` tags.

6. **Secure Code Generation & Execution**:
   - Generated code is statically checked before execution via `validate_experiment_code_safety`.
   - Forbidden: `subprocess`, `socket`, `shutil`, `urllib`, `requests`, `httpx`, `ctypes`, `eval`, `exec`, `os.environ`, `os.system`.
   - In demo mode, host subprocesses run with scrubbed minimal environments (`PATH`, `SYSTEMROOT`, `WINDIR`) so parent credentials cannot be leaked.

---

## Accessibility & Performance Constraints

- **Accessibility**:
  - High contrast ratios (exceeding WCAG AA 4.5:1) on midnight navy backgrounds.
  - Visible focus indicators on all interactive inputs, buttons, and node buttons.
  - Keyboard navigation: Full keyboard accessibility with shortcuts (`Ctrl+Enter` to start, arrow keys / tabs to select nodes).
  - External links must include `rel="noopener noreferrer"` and descriptive labels.

- **Performance**:
  - Target 60 FPS on integrated GPUs (Intel Iris Xe / AMD Radeon) with 8 GB RAM constraints.
  - Maximum particle count budgeted to <= 200 particles.
  - Dispose Three.js geometries and materials on unmount.

---

## Acceptance Criteria & Status

| Acceptance Criterion | Verification Command | Status |
| :--- | :--- | :--- |
| **Backend Unit & Integration Tests** | `pytest backend/tests -v` (49 tests) | **PASS** |
| **Frontend TypeScript Typecheck** | `npm --prefix frontend run typecheck` | **PASS** |
| **Frontend Production Build** | `npm --prefix frontend run build` | **PASS** |
| **Real Tavily Evidence Retrieval** | `tests/test_evidence.py::test_live_or_mocked_evidence` | **PASS** |
| **AST Security Sandbox Check** | `tests/test_experiment_code.py` (12 tests) | **PASS** |
| **Full 10-Stage Research Workflow** | `tests/test_e2e_workflow.py` | **PASS** |
| **Interactive 3D Graph & WebGL Fallback** | `frontend/components/3d/ResearchScene.tsx` | **PASS** |
| **Reproducibility Audit & Export** | `frontend/components/panels/ReportPanel.tsx` | **PASS** |
| **Live Nebius Serverless Compute** | Remote Cloud Job submission | **BLOCKED** (Cloud project/bucket unconfigured in `.env`) |
| **Live NVIDIA NIM Inference Key** | `POST https://integrate.api.nvidia.com/v1/chat/completions` | **BLOCKED** (nvapi- key returned HTTP 403 Forbidden) |

---

## Test & Build Commands

Execute from workspace root `D:\ResearchForge`:

```powershell
# Run all backend tests (49 passed)
.\backend\.venv\Scripts\pytest.exe backend\tests -v

# Type check TypeScript
npm --prefix frontend run typecheck

# Production build
npm --prefix frontend run build

# Start development server (port 3000)
npm --prefix frontend run dev

# Start backend (port 8000)
.\backend\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```
