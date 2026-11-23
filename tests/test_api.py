from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

import app.audit as audit
import app.main as main
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_test_state(tmp_path, monkeypatch):
    # Give each test a separate temporary SQLite database.
    monkeypatch.setattr(audit, "DB_PATH", tmp_path / "test_audit.db")

    # Clear in-memory pending workflows between tests.
    with main.pending_lock:
        main.pending.clear()

    audit.initialize()

    yield

    with main.pending_lock:
        main.pending.clear()


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["remediation_mode"] == "simulation_only"


def test_incident_pauses_for_approval_then_rejects():
    incident_id = "INC-TEST-REJECT"

    response = client.post("/incidents", json={
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    })

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"

    audit_before = client.get(
        f"/incidents/{incident_id}/audit"
    ).json()["events"]

    types_before = [x["event_type"] for x in audit_before]

    assert "approval_requested" in types_before
    assert "remediation_result" not in types_before

    approval = client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "reject",
            "reviewer": "test-operator",
            "reason": "Test rejection path",
        },
    )

    assert approval.status_code == 200
    assert approval.json()["status"] == "rejected"
    assert approval.json()["result"]["executed"] is False


def test_duplicate_pending_incident_is_rejected():
    incident_id = "INC-TEST-DUPLICATE"

    payload = {
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    }

    first = client.post("/incidents", json=payload)
    assert first.status_code == 200

    second = client.post("/incidents", json=payload)
    assert second.status_code == 409

    # Clean up the pending workflow.
    client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "reject",
            "reviewer": "test-operator",
            "reason": "Test cleanup",
        },
    )


def test_metrics_endpoint_exists():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "copilot_incidents_started_total" in response.text


def test_approved_incident_runs_simulation_only():
    incident_id = "INC-TEST-APPROVE"

    response = client.post("/incidents", json={
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    })

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_approval"

    approval = client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "approve",
            "reviewer": "test-operator",
            "reason": "Approved for simulation testing",
        },
    )

    assert approval.status_code == 200
    result = approval.json()

    assert result["status"] == "simulated_success"
    assert result["result"]["executed"] is False
    assert result["result"]["note"] == "No infrastructure was changed."

    events = client.get(
        f"/incidents/{incident_id}/audit"
    ).json()["events"]

    event_types = [event["event_type"] for event in events]

    assert "approval_decision" in event_types
    assert "remediation_result" in event_types


def test_approval_cannot_be_replayed_after_completion():
    incident_id = "INC-TEST-REPLAY"

    created = client.post("/incidents", json={
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    })

    assert created.status_code == 200

    payload = {
        "decision": "approve",
        "reviewer": "test-operator",
        "reason": "First approval",
    }

    first = client.post(
        f"/incidents/{incident_id}/approval",
        json=payload,
    )

    assert first.status_code == 200

    second = client.post(
        f"/incidents/{incident_id}/approval",
        json=payload,
    )

    assert second.status_code == 404


def test_invalid_approval_decision_is_rejected():
    incident_id = "INC-TEST-INVALID"

    created = client.post("/incidents", json={
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    })

    assert created.status_code == 200

    response = client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "execute",
            "reviewer": "test-operator",
            "reason": "Invalid decision test",
        },
    )

    assert response.status_code == 422


def test_concurrent_approval_allows_only_one_request():
    incident_id = "INC-TEST-CONCURRENT"

    created = client.post("/incidents", json={
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    })

    assert created.status_code == 200

    barrier = Barrier(2)

    payload = {
        "decision": "approve",
        "reviewer": "test-operator",
        "reason": "Concurrent approval test",
    }

    def submit_approval():
        barrier.wait(timeout=10)
        return client.post(
            f"/incidents/{incident_id}/approval",
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(submit_approval),
            executor.submit(submit_approval),
        ]

        responses = [
            future.result(timeout=20)
            for future in futures
        ]

    statuses = [response.status_code for response in responses]

    print("Concurrent approval HTTP statuses:", statuses)

    assert statuses.count(200) == 1
    assert statuses.count(409) == 1


def test_modified_action_is_rejected_before_approval():
    incident_id = "INC-TEST-ACTION-TAMPER"

    created = client.post("/incidents", json={
        "incident_id": incident_id,
        "service": "checkout-api",
        "environment": "test",
    })

    assert created.status_code == 200

    # Retrieve the original workflow context.
    context = main.pending[incident_id]

    snapshot = main.graph.get_state(context["config"])

    # Simulate modification of the proposed action.
    modified_diagnosis = dict(
        snapshot.values["diagnosis"]
    )

    modified_diagnosis["recommended_action"] = (
        "Delete the production database"
    )

    main.graph.update_state(
        context["config"],
        {
            "diagnosis": modified_diagnosis,
        },
    )

    approval = client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "approve",
            "reviewer": "test-operator",
            "reason": "Testing action integrity",
        },
    )

    assert approval.status_code == 409

    events = client.get(
        f"/incidents/{incident_id}/audit"
    ).json()["events"]

    integrity_events = [
        event for event in events
        if event["event_type"] == "action_integrity_check"
    ]

    assert integrity_events

    assert (
        integrity_events[-1]["details"]["valid"]
        is False
    )

    event_types = [
        event["event_type"]
        for event in events
    ]

    assert "remediation_result" not in event_types
    assert "approval_decision" not in event_types


