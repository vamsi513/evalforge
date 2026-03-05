from typing import Any, Dict, List, Optional

import httpx


class EvalForgeClient:
    def __init__(self, base_url: str, api_key: str = "", workspace_id: str = "default") -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.workspace_id = workspace_id.strip() or "default"

    def _headers(self) -> Dict[str, str]:
        headers = {"X-Workspace-ID": self.workspace_id}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _get(self, path: str) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            response = client.get(path, headers=self._headers())
            response.raise_for_status()
            return response.json()

    def get_health(self) -> Dict[str, Any]:
        return self._get("/health")

    def get_telemetry(self) -> Dict[str, Any]:
        return self._get("/api/v1/telemetry/summary")

    def get_datasets(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/datasets")

    def get_evaluators(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/evaluators")

    def get_experiments(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/experiments")

    def get_experiment_report(self, experiment_name: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/experiments/{experiment_name}/report")

    def get_prompt_templates(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/assets/prompts")

    def get_golden_cases(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/assets/golden-cases")

    def get_runs(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/evals")

    def get_jobs(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/evals/jobs")

    def get_release_gates(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/release-gates")

    def get_model_routes(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/model-routing")

    def get_release_gate_trends(
        self, dataset_name: str = "", experiment_name: str = "", lookback_days: int = 30
    ) -> Dict[str, Any]:
        query = f"/api/v1/release-gates/trends?lookback_days={lookback_days}"
        if dataset_name:
            query += f"&dataset_name={dataset_name}"
        if experiment_name:
            query += f"&experiment_name={experiment_name}"
        return self._get(query)
