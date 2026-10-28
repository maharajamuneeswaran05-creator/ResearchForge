# ResearchForge Operations & Deployment Guide

## 1. Operating Modes

ResearchForge supports three operating modes:

### Mode A: Full Cloud Mode (Production)
- **Inference**: NVIDIA Nemotron on Nebius Token Factory or NVIDIA NIM.
- **Evidence**: Tavily Search API.
- **Compute**: Nebius AI Cloud Serverless AI jobs.
- **Storage**: Nebius Object Storage (S3-compatible).
- **Prerequisites**: Full `.env` with all keys configured.

### Mode B: Hybrid Mode (Local Experimentation)
- **Inference**: Active NVIDIA/Nebius inference API key.
- **Evidence**: Active Tavily API key.
- **Compute**: Local Isolated Sandbox (`EXPERIMENT_DEMO_MODE=true` or via UI fallback).
- **Description**: Real literature search and real model generation; execution is simulated locally with stripped credentials and AST security checks.

### Mode C: Offline Exploration / Demo Mode
- **Inference & Evidence**: Offline / mock data via the "Explore 3D Demo" button.
- **Description**: Immediate visual demonstration of the entire 10-stage pipeline with pre-computed biological science benchmarks, ideal for network-isolated environments or quick evaluation.

---

## 2. Windows Service Management

### Starting Backend

```powershell
# From workspace root
.\backend\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

### Starting Frontend

```powershell
# From workspace root
npm --prefix frontend run dev
```

### Health Verification

- **Backend Health Check**: `GET http://localhost:8000/health` -> `{"status":"ok","service":"researchforge-backend"}`
- **Model Check**: `GET http://localhost:8000/test/nebius` -> checks connectivity with configured model.

---

## 3. Investigating Windows Execution Runner

On Windows environments, test runners or IDE tasks that invoke `powershell` directly may execute `powershell.cmd` if located in the current working directory. The `powershell.cmd` shims included in the repository redirect cleanly to `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe %*`.

---

## 4. Security & Compliance Checklist

- [x] Secrets in `backend/.env` are ignored by git and never logged.
- [x] CORS is restricted to frontend origins (`localhost:3000`).
- [x] Defensive HTTP headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`) are injected on all responses.
- [x] AST Security Validator blocks execution of untrusted system, socket, and process commands.
- [x] Local demo execution runs in isolated sub-environments with host secrets scrubbed.
