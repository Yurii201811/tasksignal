from app.api import routes


def test_health(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_process_demo_endpoint(client) -> None:
    response = client.post("/api/process/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_items_loaded"] >= 17
    assert payload["signals_detected"] >= 15
    assert payload["opportunities_created"] >= 5

    opportunities = client.get("/api/opportunities").json()
    assert len(opportunities) >= 5
    assert opportunities[0]["generated_prompt"].startswith("# Build")
    assert opportunities[0]["scoring_breakdown_json"]["rank_drivers"]
    assert opportunities[0]["evidence_items"][0]["evidence_spans"]
    assert "Ranking rationale" in opportunities[0]["generated_prompt"]


def test_process_demo_is_idempotent_without_reset(client) -> None:
    first = client.post("/api/process/demo").json()
    second = client.post("/api/process/demo").json()

    assert first["normalized_items_created"] >= 17
    assert first["opportunities_created"] >= 5
    assert second["raw_items_loaded"] >= 17
    assert second["normalized_items_created"] == 0
    assert second["opportunities_created"] == 0
    assert len(client.get("/api/opportunities").json()) >= 5
    assert client.get("/api/stats").json()["problem_signals"] == first["signals_detected"]


def test_process_demo_reset_rejects_when_token_not_configured(client) -> None:
    response = client.post("/api/process/demo?reset=true")

    assert response.status_code == 403
    assert "Demo reset requires" in response.json()["detail"]


def test_process_demo_reset_requires_token_when_configured(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "demo_reset_token", "test-reset-token")

    response = client.post("/api/process/demo?reset=true")

    assert response.status_code == 403
    assert "Demo reset requires" in response.json()["detail"]


def test_process_demo_reset_accepts_configured_token(client, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "demo_reset_token", "test-reset-token")

    response = client.post(
        "/api/process/demo?reset=true",
        headers={"X-Demo-Reset-Token": "test-reset-token"},
    )

    assert response.status_code == 200
    assert response.json()["opportunities_created"] >= 5


def test_regenerate_opportunity_rebuilds_prompt_from_evidence(client) -> None:
    client.post("/api/process/demo")
    opportunity = client.get("/api/opportunities").json()[0]

    response = client.post(f"/api/opportunities/{opportunity['id']}/regenerate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == opportunity["id"]
    assert payload["updated_at"] >= opportunity["updated_at"]
    assert payload["generated_prompt"].startswith("# Build")
    assert "Top source excerpts" in payload["generated_prompt"]
    assert payload["scoring_breakdown_json"]["common_phrases"]
    assert payload["problem_statement"].count("People repeatedly describe") == 1
