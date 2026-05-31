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
