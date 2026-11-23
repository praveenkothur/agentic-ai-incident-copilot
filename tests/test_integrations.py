
import json
from unittest.mock import Mock

import pytest
import requests

import app.evidence as evidence
import app.local_llm as local_llm
import app.security as security


@pytest.fixture
def evidence_data(tmp_path, monkeypatch):
    logs = [
        {
            "service": "checkout-api",
            "message": "Payment request timeout",
        },
        {
            "service": "checkout-api",
            "message": "Payment API timed out",
        },
        {
            "service": "checkout-api",
            "message": "HTTP 500 error",
        },
        {
            "service": "other-service",
            "message": "Connection timeout",
        },
    ]

    deployments = [
        {
            "service": "checkout-api",
            "version": "2.4",
        },
        {
            "service": "other-service",
            "version": "1.0",
        },
    ]

    (tmp_path / "logs.json").write_text(
        json.dumps(logs), encoding="utf-8"
    )
    (tmp_path / "deployments.json").write_text(
        json.dumps(deployments), encoding="utf-8"
    )

    monkeypatch.setattr(evidence, "DATA_DIR", tmp_path)

    return tmp_path


def test_fixture_evidence_without_prometheus(
    evidence_data, monkeypatch
):
    monkeypatch.delenv("PROMETHEUS_URL", raising=False)

    result = evidence.get_evidence("checkout-api")

    assert result["service"] == "checkout-api"
    assert len(result["logs"]) == 3
    assert len(result["deployments"]) == 1
    assert result["dependency"]["observed_timeouts"] == 2
    assert result["metrics"]["source"] == "simulated_fixture"
    assert result["metrics"]["http_5xx_rate"] is None
    assert result["warnings"] == []


def test_prometheus_success_response(
    evidence_data, monkeypatch
):
    monkeypatch.setenv(
        "PROMETHEUS_URL", "http://localhost:9090/"
    )

    response = Mock()
    response.json.return_value = {
        "status": "success",
        "data": {
            "result": [
                {"value": [1234567890, "0.25"]}
            ]
        },
    }

    get_mock = Mock(return_value=response)
    monkeypatch.setattr(evidence.requests, "get", get_mock)

    result = evidence.get_evidence("checkout-api")

    assert result["metrics"]["source"] == "prometheus"
    assert result["metrics"]["http_5xx_rate"] == [
        {"value": [1234567890, "0.25"]}
    ]
    assert result["warnings"] == []

    get_mock.assert_called_once()
    assert get_mock.call_args.kwargs["timeout"] == 2
    assert get_mock.call_args.args[0] == (
        "http://localhost:9090/api/v1/query"
    )


def test_prometheus_non_success_response(
    evidence_data, monkeypatch
):
    monkeypatch.setenv(
        "PROMETHEUS_URL", "http://localhost:9090"
    )

    response = Mock()
    response.json.return_value = {
        "status": "error"
    }

    monkeypatch.setattr(
        evidence.requests,
        "get",
        Mock(return_value=response),
    )

    result = evidence.get_evidence("checkout-api")

    assert result["metrics"]["source"] == "simulated_fixture"
    assert (
        "Prometheus returned a non-success response."
        in result["warnings"]
    )


def test_prometheus_connection_failure(
    evidence_data, monkeypatch
):
    monkeypatch.setenv(
        "PROMETHEUS_URL", "http://localhost:9090"
    )

    monkeypatch.setattr(
        evidence.requests,
        "get",
        Mock(side_effect=requests.ConnectionError),
    )

    result = evidence.get_evidence("checkout-api")

    assert result["metrics"]["source"] == "simulated_fixture"
    assert any(
        "Prometheus unavailable" in warning
        and "ConnectionError" in warning
        for warning in result["warnings"]
    )


def test_local_llm_success(monkeypatch):
    model_instance = Mock()
    model_instance.invoke.return_value.content = (
        "The checkout service is experiencing payment timeouts."
    )

    model_constructor = Mock(return_value=model_instance)

    monkeypatch.setattr(
        local_llm, "ChatOllama", model_constructor
    )
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    monkeypatch.setenv(
        "OLLAMA_BASE_URL", "http://localhost:11434"
    )

    evidence_data = {
        "service": "checkout-api",
        "logs": ["payment timeout"],
    }

    diagnosis = {
        "likely_root_cause": "Payment dependency timeout",
        "confidence": 0.85,
    }

    result = local_llm.explain_with_local_llm(
        evidence_data, diagnosis
    )

    assert "payment timeouts" in result

    model_constructor.assert_called_once_with(
        model="qwen2.5:3b",
        base_url="http://localhost:11434",
        temperature=0,
    )

    model_instance.invoke.assert_called_once()

    prompt = model_instance.invoke.call_args.args[0]
    assert "Evidence JSON:" in prompt
    assert "Deterministic findings JSON:" in prompt
    assert "payment timeout" in prompt


def test_local_llm_uses_default_configuration(monkeypatch):
    model_instance = Mock()
    model_instance.invoke.return_value.content = "Analysis complete."

    model_constructor = Mock(return_value=model_instance)

    monkeypatch.setattr(
        local_llm, "ChatOllama", model_constructor
    )
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    result = local_llm.explain_with_local_llm({}, {})

    assert result == "Analysis complete."

    model_constructor.assert_called_once_with(
        model="qwen2.5:3b",
        base_url="http://localhost:11434",
        temperature=0,
    )


def test_local_llm_failure_propagates(monkeypatch):
    model_instance = Mock()
    model_instance.invoke.side_effect = ConnectionError(
        "Ollama unavailable"
    )

    monkeypatch.setattr(
        local_llm,
        "ChatOllama",
        Mock(return_value=model_instance),
    )

    with pytest.raises(ConnectionError, match="Ollama unavailable"):
        local_llm.explain_with_local_llm({}, {})


def test_security_rejects_empty_digest():
    assert security.verify_action_digest(
        "INC-001",
        "Review and simulate rollback",
        "",
    ) is False


def test_security_accepts_valid_digest():
    incident_id = "INC-002"
    action = "Review and simulate rollback"

    digest = security.action_digest(incident_id, action)

    assert security.verify_action_digest(
        incident_id, action, digest
    ) is True


def test_security_rejects_modified_action():
    incident_id = "INC-003"
    original_action = "Review and simulate rollback"

    digest = security.action_digest(
        incident_id, original_action
    )

    assert security.verify_action_digest(
        incident_id,
        "Delete production database",
        digest,
    ) is False


def test_security_rejects_different_incident():
    action = "Review and simulate rollback"

    digest = security.action_digest("INC-004", action)

    assert security.verify_action_digest(
        "INC-005", action, digest
    ) is False
