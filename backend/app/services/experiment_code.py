"""Experiment code generation: Experiment Plan -> runnable Python script."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.schemas.research import ExperimentCodeResponse, ExperimentPlanResponse
from app.services.nebius import NebiusClient, NebiusError
from app.services.research_gap import ResearchGapError, ResearchGapService

import ast

logger = logging.getLogger(__name__)

_PYTHON_SIGNAL = re.compile(
    r"\b(import |from |def |class |if __name__\s*==)",
    re.MULTILINE,
)

DISALLOWED_MODULES = {
    "subprocess",
    "socket",
    "shutil",
    "urllib",
    "urllib3",
    "requests",
    "httpx",
    "aiohttp",
    "ctypes",
    "builtins",
    "posix",
    "nt",
    "pty",
}

DISALLOWED_CALLS = {
    "eval",
    "exec",
    "__import__",
    "breakpoint",
}

DISALLOWED_OS_ATTRS = {
    "system",
    "popen",
    "spawn",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
    "remove",
    "unlink",
    "rmdir",
    "removedirs",
    "environ",
    "getenv",
    "putenv",
    "kill",
}


def validate_experiment_code_safety(code: str) -> tuple[bool, str | None]:
    """Inspect Python AST for potentially unsafe operations and host privilege escalation."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"Syntax error in experiment code: {exc}"

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_root = alias.name.split(".")[0]
                if mod_root in DISALLOWED_MODULES:
                    return False, f"Forbidden module import: '{alias.name}'"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod_root = node.module.split(".")[0]
                if mod_root in DISALLOWED_MODULES:
                    return False, f"Forbidden module import: '{node.module}'"
                if mod_root == "os":
                    for alias in node.names:
                        if alias.name in DISALLOWED_OS_ATTRS:
                            return False, f"Forbidden os function import: '{alias.name}'"

        # Check function calls
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in DISALLOWED_CALLS:
                    return False, f"Forbidden built-in function call: '{node.func.id}()'"
            elif isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                    if node.func.attr in DISALLOWED_OS_ATTRS:
                        return False, f"Forbidden os function call: 'os.{node.func.attr}()'"

        # Check attribute access on os.environ
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                if node.attr in DISALLOWED_OS_ATTRS:
                    return False, f"Forbidden access to sensitive host attribute: 'os.{node.attr}'"

    return True, None


class ExperimentCodeError(Exception):
    """Raised when experiment code generation fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ExperimentCodeService:
    """Generate a reproducible Python experiment script from a validated plan."""

    def __init__(self, nebius_client: NebiusClient) -> None:
        self._nebius = nebius_client

    async def generate(self, plan: ExperimentPlanResponse) -> ExperimentCodeResponse:
        system_message = (
            "You are a research software engineer. Generate a single runnable Python "
            "experiment script from a validated experiment plan.\n"
            "Return ONLY a valid JSON object. No markdown outside JSON string fields."
        )
        user_message = self._build_prompt(plan)

        try:
            payload = await self._nebius.chat_completion(
                user_message=user_message,
                system_message=system_message,
                max_tokens=3500,
                temperature=0.1,
            )
            raw_text = self._nebius.extract_assistant_text(payload)
        except NebiusError as exc:
            raise ExperimentCodeError(
                f"Nemotron code generation failed: {exc}",
                status_code=exc.status_code,
            ) from exc

        try:
            data = ResearchGapService._extract_json(raw_text)
        except ResearchGapError as exc:
            raise ExperimentCodeError(
                f"Failed to parse code-generation JSON: {exc}",
                status_code=exc.status_code or 502,
            ) from exc

        return self._build_response(plan, data)

    @staticmethod
    def _build_prompt(plan: ExperimentPlanResponse) -> str:
        metrics = ", ".join(plan.evaluation_metrics)
        datasets = "; ".join(plan.dataset_requirements)
        risks = "; ".join(plan.risks) if plan.risks else "none listed"
        variables = (
            f"independent={plan.variables.independent}; "
            f"dependent={plan.variables.dependent}; "
            f"controls={plan.variables.controls}"
        )
        return (
            f"Research Question: {plan.research_question}\n"
            f"Hypothesis: {plan.hypothesis}\n"
            f"Objective: {plan.research_objective}\n"
            f"Variables: {variables}\n"
            f"Baseline: {plan.baseline}\n"
            f"Method: {plan.proposed_method}\n"
            f"Dataset requirements: {datasets}\n"
            f"Evaluation metrics: {metrics}\n"
            f"Expected outcome: {plan.expected_outcome}\n"
            f"Risks: {risks}\n\n"
            "Respond with ONLY this JSON schema:\n"
            "{\n"
            '  "code": "full python script as a string",\n'
            '  "dependencies": ["numpy", "scikit-learn"],\n'
            '  "entrypoint": "python experiment.py",\n'
            '  "random_seed": 42,\n'
            '  "inputs": ["description of required inputs"],\n'
            '  "outputs": ["description of produced outputs"],\n'
            '  "notes": "optional short note"\n'
            "}\n\n"
            "Hard requirements for the Python code string:\n"
            "- Implement the experiment described by the plan (baseline comparison required).\n"
            "- Use a fixed RANDOM_SEED = 42 (or the provided random_seed) wherever randomness applies.\n"
            "- Clearly document dependencies in comments near the top (pip-installable names).\n"
            "- Clearly document inputs and outputs in comments.\n"
            "- Prefer synthetic/local demo data if external datasets are unavailable.\n"
            "- Do NOT perform network requests (no urllib/requests/httpx/openai API calls).\n"
            "- Do NOT read/write arbitrary filesystem paths outside a local ./artifacts directory.\n"
            "- Do NOT use subprocess, os.system, os.environ, eval, or exec.\n"
            "- Include if __name__ == '__main__': entrypoint.\n"
            "- Print numerical evaluation metrics to stdout using the standard telemetry format:\n"
            "    METRIC <metric_name>=<numeric_value>\n"
            "  For example: print(f\"METRIC accuracy={acc:.4f}\") so the platform parses them.\n"
            "- Keep comments only where useful.\n"
            "- The code field must contain valid Python source, not natural language.\n"
        )

    def _build_response(
        self, plan: ExperimentPlanResponse, data: dict[str, Any]
    ) -> ExperimentCodeResponse:
        code = self._extract_python_code(data.get("code"))
        if not self._looks_like_python(code):
            raise ExperimentCodeError(
                "Generated response did not contain valid Python code.",
                status_code=502,
            )

        is_safe, safety_err = validate_experiment_code_safety(code)
        if not is_safe:
            raise ExperimentCodeError(
                f"Generated experiment code failed security policy: {safety_err}",
                status_code=422,
            )

        try:
            seed = int(data.get("random_seed", 42))
        except (TypeError, ValueError):
            seed = 42

        dependencies = [
            str(d).strip()
            for d in (data.get("dependencies") or [])
            if str(d).strip()
        ]
        inputs = [
            str(i).strip() for i in (data.get("inputs") or []) if str(i).strip()
        ]
        outputs = [
            str(o).strip() for o in (data.get("outputs") or []) if str(o).strip()
        ]
        entrypoint = str(data.get("entrypoint") or "python experiment.py").strip()
        notes_raw = data.get("notes")
        notes = str(notes_raw).strip() if notes_raw else None

        return ExperimentCodeResponse(
            research_question=plan.research_question,
            language="python",
            code=code,
            dependencies=dependencies,
            entrypoint=entrypoint,
            random_seed=seed,
            inputs=inputs,
            outputs=outputs,
            model=self._nebius.model,
            notes=notes,
        )

    @staticmethod
    def _extract_python_code(raw: Any) -> str:
        if raw is None:
            raise ExperimentCodeError(
                "Generated response missing code field.",
                status_code=502,
            )
        text = str(raw).strip()
        if not text:
            raise ExperimentCodeError(
                "Generated code field was empty.",
                status_code=502,
            )

        fence = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
        if fence:
            return fence.group(1).strip()
        return text

    @staticmethod
    def _looks_like_python(code: str) -> bool:
        if len(code) < 40:
            return False
        return _PYTHON_SIGNAL.search(code) is not None
