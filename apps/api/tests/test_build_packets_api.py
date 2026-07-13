from __future__ import annotations

import io
import json
import zipfile
from uuid import UUID

from sqlalchemy.orm import Session

from app.api import routes
from app.db.session import engine
from app.models.all_models import BuildPacket
from app.services.build_packets.enhancement import ENHANCEABLE_FILENAMES
from app.services.generation.enhancement import EnhancementUnavailable
from app.services.ingestion.connectors import BaseConnector
from app.services.ingestion.types import RawFetchedItem, utc_now
from app.workers import scan_pipeline


class PacketConnector(BaseConnector):
    name = "packetapi"

    def fetch(self, query: str = "", limit: int = 50) -> list[RawFetchedItem]:
        return [
            RawFetchedItem(
                source="packetapi",
                external_id=f"packet-{index}",
                raw_json={
                    "title": f"Manual release evidence {index}",
                    "body": (
                        "Builders manually copy release failures every week. "
                        "It takes forever and they would pay for a focused workflow."
                    ),
                    "created_at": "2026-07-11T00:00:00Z",
                    "url": f"https://example.test/evidence/{index}",
                    "author": f"private-author-{index}",
                },
                fetched_at=utc_now(),
            )
            for index in range(2)
        ][:limit]


def create_packet_candidate(client, monkeypatch) -> tuple[dict, list[dict]]:
    monkeypatch.setattr(routes, "PUBLIC_SCAN_API_SOURCES", {"fixture", "packetapi"})
    monkeypatch.setattr(routes.settings, "public_scan_sources", "fixture,packetapi")
    monkeypatch.setitem(scan_pipeline.CONNECTOR_FACTORIES, "packetapi", PacketConnector)
    project_response = client.post(
        "/api/v1/research-projects",
        json={
            "name": "Packet research",
            "source_type": "packetapi",
            "query": "release pain",
            "limit": 10,
            "cadence": "manual",
            "labels": [],
            "enabled": True,
        },
    )
    assert project_response.status_code == 200, project_response.text
    project = project_response.json()
    run = client.post(f"/api/v1/research-projects/{project['id']}/run")
    assert run.status_code == 200, run.text
    thread = client.get(
        f"/api/v1/opportunity-threads?project_id={project['id']}"
    ).json()[0]
    decision = client.patch(
        f"/api/v1/opportunity-threads/{thread['id']}/decision",
        json={
            "review_state": "build_candidate",
            "review_note": "LOCAL-ONLY-NOTE-DO-NOT-EXPORT",
            "expected_version": thread["version"],
        },
    )
    assert decision.status_code == 200, decision.text
    thread = decision.json()
    return thread, thread["current_snapshot"]["evidence_items"]


def test_build_packet_requires_ready_build_candidate_and_is_immutable_downloadable(
    client,
    monkeypatch,
) -> None:
    thread, evidence = create_packet_candidate(client, monkeypatch)

    weak = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert weak.status_code == 409
    assert "readiness" in weak.json()["detail"].lower()

    label = client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "true_signal"},
    )
    assert label.status_code == 200, label.text

    created = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert created.status_code == 201, created.text
    packet = created.json()
    readiness = client.get("/api/v1/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["checks"]["build_packets"] == 1
    assert packet["generation_mode"] == "deterministic"
    assert packet["thread_id"] == thread["id"]
    assert packet["snapshot_id"] == thread["current_snapshot"]["id"]
    assert {artifact["path"] for artifact in packet["artifacts"]} == {
        "README.md",
        "MANIFEST.json",
        "opportunity.json",
        "evidence.md",
        "task-pack.md",
        "product-requirements.md",
        "validation-plan.md",
        "github-issue.md",
        "implementation-plan.md",
        "agent-brief.md",
    }
    serialized = str(packet)
    assert "LOCAL-ONLY-NOTE-DO-NOT-EXPORT" not in serialized
    assert "private-author" not in serialized
    assert packet["manifest"]["decision_event_id"]
    opportunity_artifact = next(
        artifact for artifact in packet["artifacts"] if artifact["path"] == "opportunity.json"
    )
    opportunity_payload = json.loads(opportunity_artifact["content"])
    assert opportunity_payload["opportunity"]["decision"]["next_state"] == "build_candidate"
    assert "previous_note" not in opportunity_payload["opportunity"]["decision"]

    listed = client.get(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets"
    )
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [packet["id"]]
    assert "artifacts" not in listed.json()[0]
    assert listed.json()[0]["artifact_count"] == 10

    fetched = client.get(f"/api/v1/build-packets/{packet['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == packet

    verified = client.get(f"/api/v1/build-packets/{packet['id']}/verify")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["missing_files"] == []
    assert verified.json()["unexpected_files"] == []
    assert verified.json()["mismatched_files"] == []

    downloaded = client.get(f"/api/v1/build-packets/{packet['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert set(archive.namelist()) == {
            artifact["path"] for artifact in packet["artifacts"]
        }

    openapi = client.get("/openapi.json").json()
    download_schema = openapi["paths"]["/api/v1/build-packets/{packet_id}/download"][
        "get"
    ]["responses"]["200"]["content"]
    assert "application/zip" in download_schema
    assert "application/json" not in download_schema


def test_build_packet_rejects_sensitive_risk_and_non_candidate(client, monkeypatch) -> None:
    thread, evidence = create_packet_candidate(client, monkeypatch)
    for item in evidence:
        response = client.post(
            "/api/v1/labels",
            json={"item_id": item["id"], "label": "true_signal"},
        )
        assert response.status_code == 200
    sensitive = client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "sensitive_risk"},
    )
    assert sensitive.status_code == 200

    blocked = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert blocked.status_code == 409
    assert "sensitive" in blocked.json()["detail"].lower()

    cleared = client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "true_signal"},
    )
    assert cleared.status_code == 200
    latest = client.get(f"/api/v1/opportunity-threads/{thread['id']}").json()
    update = client.patch(
        f"/api/v1/opportunity-threads/{thread['id']}/decision",
        json={"review_state": "promising", "expected_version": latest["version"]},
    )
    assert update.status_code == 200

    blocked = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert blocked.status_code == 409
    assert "build_candidate" in blocked.json()["detail"]


def test_configured_ai_adds_only_fixed_enhanced_variants_and_falls_back_safely(
    client,
    monkeypatch,
) -> None:
    thread, evidence = create_packet_candidate(client, monkeypatch)
    label = client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "true_signal"},
    )
    assert label.status_code == 200
    monkeypatch.setattr(routes.settings, "operator_scan_token", "packet-token")

    denied = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={"use_configured_ai": True},
    )
    assert denied.status_code == 403

    captured: list[str] = []

    def enhance(prompt: str) -> tuple[str, str, str]:
        captured.append(prompt)
        return (
            "ollama",
            "qwen-test",
            json.dumps(
                {name: f"# Enhanced {name}\n\nSafer implementation detail." for name in ENHANCEABLE_FILENAMES}
            ),
        )

    monkeypatch.setattr(routes, "enhance_prompt", enhance)
    created = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={"use_configured_ai": True},
        headers={"X-Operator-Scan-Token": "packet-token"},
    )
    assert created.status_code == 201, created.text
    packet = created.json()
    assert packet["generation_mode"] == "configured_ai"
    assert packet["enhancement_status"] == "generated"
    assert packet["enhancement_provider"] == "ollama"
    assert packet["enhancement_model"] == "qwen-test"
    assert packet["manifest"]["file_count"] == 16
    assert {artifact["path"] for artifact in packet["artifacts"] if artifact["path"].startswith("enhanced/")} == {
        f"enhanced/{name}" for name in ENHANCEABLE_FILENAMES
    }
    assert len(captured) == 1
    assert "private-author" not in captured[0]
    assert "LOCAL-ONLY-NOTE-DO-NOT-EXPORT" not in captured[0]
    assert client.get(f"/api/v1/build-packets/{packet['id']}/verify").json()["valid"] is True

    def unavailable(_prompt: str) -> tuple[str, str, str]:
        raise EnhancementUnavailable("SECRET-PROVIDER-DETAIL")

    monkeypatch.setattr(routes, "enhance_prompt", unavailable)
    fallback = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={"use_configured_ai": True},
        headers={"X-Operator-Scan-Token": "packet-token"},
    )
    assert fallback.status_code == 201, fallback.text
    fallback_packet = fallback.json()
    assert fallback_packet["generation_mode"] == "configured_ai"
    assert fallback_packet["enhancement_status"] == "fallback"
    assert fallback_packet["manifest"]["enhancement"]["failure_code"] == "unavailable"
    assert "SECRET-PROVIDER-DETAIL" not in fallback.text
    assert not any(
        artifact["path"].startswith("enhanced/")
        for artifact in fallback_packet["artifacts"]
    )


def test_download_refuses_tampered_stored_packet(client, monkeypatch) -> None:
    thread, evidence = create_packet_candidate(client, monkeypatch)
    assert client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "true_signal"},
    ).status_code == 200
    packet = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    ).json()

    with Session(engine) as db:
        stored = db.get(BuildPacket, UUID(packet["id"]))
        assert stored is not None
        artifacts = dict(stored.artifacts_json)
        artifacts["README.md"] += "tampered\n"
        stored.artifacts_json = artifacts
        db.commit()

    verified = client.get(f"/api/v1/build-packets/{packet['id']}/verify")
    assert verified.status_code == 200
    assert verified.json()["valid"] is False
    assert "README.md" in verified.json()["mismatched_files"]
    refused = client.get(f"/api/v1/build-packets/{packet['id']}/download")
    assert refused.status_code == 409

    with Session(engine) as db:
        stored = db.get(BuildPacket, UUID(packet["id"]))
        assert stored is not None
        stored.artifacts_json = {
            artifact["path"]: artifact["content"]
            for artifact in packet["artifacts"]
            if artifact["path"] != "MANIFEST.json"
        }
        manifest = dict(stored.manifest_json)
        manifest["generated_at"] = "2000-01-01T00:00:00Z"
        stored.manifest_json = manifest
        stored.manifest_sha256 = routes.packet_sha256(
            routes.canonical_packet_json(manifest)
        )
        db.commit()
    metadata_tamper = client.get(f"/api/v1/build-packets/{packet['id']}/verify").json()
    assert metadata_tamper["valid"] is False
    assert "manifest metadata mismatch for generated_at" in metadata_tamper["errors"]
    assert "generated_at" not in metadata_tamper["mismatched_files"]


def test_regenerated_snapshot_keeps_packet_run_lineage(client, monkeypatch) -> None:
    thread, evidence = create_packet_candidate(client, monkeypatch)
    assert client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "true_signal"},
    ).status_code == 200
    regenerated = client.post(
        f"/api/v1/opportunities/{thread['current_snapshot']['id']}/regenerate"
    )
    assert regenerated.status_code == 200, regenerated.text

    packet = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert packet.status_code == 201, packet.text
    assert packet.json()["lineage_status"] == "complete"
    assert packet.json()["project_id"] is not None
    assert packet.json()["run_id"] is not None
    opportunity_artifact = next(
        artifact
        for artifact in packet.json()["artifacts"]
        if artifact["path"] == "opportunity.json"
    )
    evidence_rows = json.loads(opportunity_artifact["content"])["evidence"]
    assert {row["run_ids"][0] for row in evidence_rows} == {packet.json()["run_id"]}
    assert all(row["scan_ids"] for row in evidence_rows)


def test_packet_uses_state_decision_not_latest_detach_event(client, monkeypatch) -> None:
    thread, evidence = create_packet_candidate(client, monkeypatch)
    assert client.post(
        "/api/v1/labels",
        json={"item_id": evidence[0]["id"], "label": "true_signal"},
    ).status_code == 200
    project_id = thread["project_id"]
    assert client.post(f"/api/v1/research-projects/{project_id}/run").status_code == 200
    current = client.get(f"/api/v1/opportunity-threads/{thread['id']}").json()
    assert current["snapshot_count"] == 2
    detached = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/snapshots/{current['current_snapshot']['id']}/detach",
        json={"expected_version": current["version"]},
    )
    assert detached.status_code == 200, detached.text
    source = detached.json()["source_thread"]
    assert source["decision_history"][-1]["event_type"] == "snapshot_detached"
    state_event = next(
        event
        for event in reversed(source["decision_history"])
        if event["event_type"] == "decision_changed"
    )

    packet = client.post(
        f"/api/v1/opportunity-threads/{thread['id']}/build-packets",
        json={},
    )
    assert packet.status_code == 201, packet.text
    assert packet.json()["manifest"]["decision_event_id"] == state_event["id"]
