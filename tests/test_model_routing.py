from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_model_routing_registry_and_resolution() -> None:
    headers = {"X-Workspace-ID": "routing-team"}
    use_case = f"incident_summarization_{uuid4().hex[:6]}"

    create_policy = client.post(
        "/api/v1/model-routing",
        headers=headers,
        json={
            "use_case": use_case,
            "version": "v1",
            "primary_provider": "openai",
            "primary_model": "gpt-4o-mini",
            "fallback_provider": "anthropic",
            "fallback_model": "claude-3-5-haiku",
            "max_latency_ms": 1200,
            "max_cost_usd": 0.02,
            "status": "active",
            "notes": "Default route for incident summarization flows.",
        },
    )
    assert create_policy.status_code == 201
    assert create_policy.json()["workspace_id"] == "routing-team"

    list_policies = client.get("/api/v1/model-routing", headers=headers)
    assert list_policies.status_code == 200
    assert any(policy["use_case"] == use_case for policy in list_policies.json())

    resolve = client.get(
        "/api/v1/model-routing/resolve",
        headers=headers,
        params={"use_case": use_case},
    )
    assert resolve.status_code == 200
    payload = resolve.json()
    assert payload["workspace_id"] == "routing-team"
    assert payload["use_case"] == use_case
    assert payload["selected_provider"] == "openai"
    assert payload["selected_model"] == "gpt-4o-mini"
    assert payload["status"] == "active"

