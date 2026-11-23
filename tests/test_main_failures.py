
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import app.main as main
import app.audit as audit


@pytest.fixture
def failure_client(tmp_path, monkeypatch):
    monkeypatch.setattr(
        audit,
        "DB_PATH",
        tmp_path / "failure_test_audit.db",
    )

    main.initialize()
    main.pending.clear()

    with TestClient(main.app) as test_client:
        yield test_client

    main.pending.clear()


def test_incident_graph_failure_cleans_pending(
    failure_client, monkeypatch
):
    monkeypatch.setattr(
        main.graph,
        "invoke",
        Mock(side_effect=RuntimeError("Graph failure")),
    )

    response = failure_client.post(
        "/incidents",
        json={
            "incident_id": "INC-GRAPH-FAIL",
            "service": "checkout-api",
            "environment": "test",
        },
    )

    assert response.status_code == 500
    assert "INC-GRAPH-FAIL" not in main.pending

    events = failure_client.get(
        "/incidents/INC-GRAPH-FAIL/audit"
    ).json()["events"]

    assert any(
        event["event_type"] == "investigation_error"
        for event in events
    )


def test_incident_without_interrupt_is_rejected(
    failure_client, monkeypatch
):
    monkeypatch.setattr(
        main.graph,
        "invoke",
        Mock(return_value={}),
    )

    response = failure_client.post(
        "/incidents",
        json={
            "incident_id": "INC-NO-INTERRUPT",
            "service": "checkout-api",
            "environment": "test",
        },
    )

    assert response.status_code == 500
    assert "INC-NO-INTERRUPT" not in main.pending


def test_initial_action_integrity_failure(
    failure_client, monkeypatch
):
    interrupt_value = {
        "proposed_action": "Review and simulate rollback",
        "diagnosis": {"confidence": 0.78},
    }

    monkeypatch.setattr(
        main.graph,
        "invoke",
        Mock(
            return_value={
                "__interrupt__": [
                    SimpleNamespace(value=interrupt_value)
                ]
            }
        ),
    )

    monkeypatch.setattr(
        main.graph,
        "get_state",
        Mock(
            return_value=SimpleNamespace(
                values={
                    "incident_id": "INC-WRONG-ID",
                    "diagnosis": {
                        "recommended_action": "Review and simulate rollback"
                    },
                }
            )
        ),
    )

    response = failure_client.post(
        "/incidents",
        json={
            "incident_id": "INC-INITIAL-INTEGRITY",
            "service": "checkout-api",
            "environment": "test",
        },
    )

    assert response.status_code == 409
    assert "INC-INITIAL-INTEGRITY" not in main.pending


def test_pending_context_missing_after_checkpoint(
    failure_client, monkeypatch
):
    interrupt_value = {
        "proposed_action": "Review and simulate rollback",
        "diagnosis": {"confidence": 0.78},
    }

    monkeypatch.setattr(
        main.graph,
        "invoke",
        Mock(
            return_value={
                "__interrupt__": [
                    SimpleNamespace(value=interrupt_value)
                ]
            }
        ),
    )

    monkeypatch.setattr(
        main.graph,
        "get_state",
        Mock(
            return_value=SimpleNamespace(
                values={
                    "incident_id": "INC-CONTEXT-LOST",
                    "diagnosis": {
                        "recommended_action": "Review and simulate rollback"
                    },
                }
            )
        ),
    )

    original_digest = main.action_digest

    def remove_context_before_digest(incident_id, action):
        with main.pending_lock:
            main.pending.pop(incident_id, None)
        return original_digest(incident_id, action)

    monkeypatch.setattr(
        main,
        "action_digest",
        remove_context_before_digest,
    )

    response = failure_client.post(
        "/incidents",
        json={
            "incident_id": "INC-CONTEXT-LOST",
            "service": "checkout-api",
            "environment": "test",
        },
    )

    assert response.status_code == 409


def test_approval_for_unknown_incident_returns_404(
    failure_client,
):
    response = failure_client.post(
        "/incidents/INC-UNKNOWN/approval",
        json={
            "decision": "approve",
            "reviewer": "test-reviewer",
            "reason": "Testing missing incident",
        },
    )

    assert response.status_code == 404


def test_approval_integrity_failure_marks_context_failed(
    failure_client, monkeypatch
):
    incident_id = "INC-APPROVAL-INTEGRITY"

    main.pending[incident_id] = {
        "status": "pending",
        "config": {"configurable": {"thread_id": "test-thread"}},
        "proposed_action": "Review and simulate rollback",
        "action_digest": "invalid-digest",
    }

    monkeypatch.setattr(
        main.graph,
        "get_state",
        Mock(
            return_value=SimpleNamespace(
                values={
                    "incident_id": incident_id,
                    "diagnosis": {
                        "recommended_action": "Delete production database"
                    },
                }
            )
        ),
    )

    response = failure_client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "approve",
            "reviewer": "test-reviewer",
            "reason": "Testing integrity rejection",
        },
    )

    assert response.status_code == 409
    assert main.pending[incident_id]["status"] == "failed"


def test_graph_resume_failure_is_recorded(
    failure_client, monkeypatch
):
    incident_id = "INC-RESUME-FAIL"
    action = "Review and simulate rollback"

    main.pending[incident_id] = {
        "status": "pending",
        "config": {"configurable": {"thread_id": "test-thread"}},
        "proposed_action": action,
        "action_digest": main.action_digest(incident_id, action),
    }

    monkeypatch.setattr(
        main.graph,
        "get_state",
        Mock(
            return_value=SimpleNamespace(
                values={
                    "incident_id": incident_id,
                    "diagnosis": {
                        "recommended_action": action
                    },
                }
            )
        ),
    )

    monkeypatch.setattr(
        main.graph,
        "invoke",
        Mock(side_effect=RuntimeError("Resume failed")),
    )

    response = failure_client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "approve",
            "reviewer": "test-reviewer",
            "reason": "Testing resume failure",
        },
    )

    assert response.status_code == 500
    assert main.pending[incident_id]["status"] == "failed"

    events = failure_client.get(
        f"/incidents/{incident_id}/audit"
    ).json()["events"]

    assert any(
        event["event_type"] == "resume_error"
        for event in events
    )


def test_approval_missing_remediation_uses_fallback(
    failure_client, monkeypatch
):
    incident_id = "INC-MISSING-REMEDIATION"
    action = "Review and simulate rollback"

    main.pending[incident_id] = {
        "status": "pending",
        "config": {"configurable": {"thread_id": "test-thread"}},
        "proposed_action": action,
        "action_digest": main.action_digest(incident_id, action),
    }

    monkeypatch.setattr(
        main.graph,
        "get_state",
        Mock(
            return_value=SimpleNamespace(
                values={
                    "incident_id": incident_id,
                    "diagnosis": {
                        "recommended_action": action
                    },
                }
            )
        ),
    )

    monkeypatch.setattr(
        main.graph,
        "invoke",
        Mock(return_value={}),
    )

    response = failure_client.post(
        f"/incidents/{incident_id}/approval",
        json={
            "decision": "approve",
            "reviewer": "test-reviewer",
            "reason": "Testing fallback result",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "unknown"
    assert response.json()["result"]["executed"] is False
    assert incident_id not in main.pending


def test_audit_endpoint_returns_events(failure_client):
    incident_id = "INC-AUDIT-READ"

    audit.record(
        incident_id,
        "test_event",
        "test",
        {"message": "Audit retrieval test"},
    )

    response = failure_client.get(
        f"/incidents/{incident_id}/audit"
    )

    assert response.status_code == 200
    assert response.json()["incident_id"] == incident_id
    assert any(
        event["event_type"] == "test_event"
        for event in response.json()["events"]
    )
