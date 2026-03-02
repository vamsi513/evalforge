from typing import Any, Dict, List

import httpx


class EvalForgeClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=10.0) as client:
            response = client.get(path)
            response.raise_for_status()
            return response.json()

    def get_health(self) -> Dict[str, Any]:
        return self._get("/health")

    def get_telemetry(self) -> Dict[str, Any]:
        return self._get("/api/v1/telemetry/summary")

    def get_datasets(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/datasets")

    def get_prompt_templates(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/assets/prompts")

    def get_golden_cases(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/assets/golden-cases")

    def get_runs(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/evals")

    def get_jobs(self) -> List[Dict[str, Any]]:
        return self._get("/api/v1/evals/jobs")
