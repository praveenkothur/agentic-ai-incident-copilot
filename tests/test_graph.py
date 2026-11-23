
import app.graph as graph_module
import app.local_llm as local_llm


def test_optional_llm_explanation_success(monkeypatch):
    monkeypatch.setenv("ENABLE_LLM", "true")

    monkeypatch.setattr(
        local_llm,
        "explain_with_local_llm",
        lambda evidence, diagnosis: "LLM explanation generated.",
    )

    state = {
        "evidence": {"service": "checkout-api"},
        "diagnosis": {"confidence": 0.78},
    }

    result = graph_module.optional_llm_explanation(state)

    assert result["llm_explanation"] == (
        "LLM explanation generated."
    )


def test_optional_llm_failure_preserves_deterministic_findings(
    monkeypatch,
):
    monkeypatch.setenv("ENABLE_LLM", "true")

    def failing_llm(evidence, diagnosis):
        raise RuntimeError("Simulated Ollama failure")

    monkeypatch.setattr(
        local_llm,
        "explain_with_local_llm",
        failing_llm,
    )

    state = {
        "evidence": {"service": "checkout-api"},
        "diagnosis": {"confidence": 0.78},
    }

    result = graph_module.optional_llm_explanation(state)

    assert "Local LLM unavailable (RuntimeError)" in (
        result["llm_explanation"]
    )
    assert "deterministic findings retained" in (
        result["llm_explanation"]
    )


def test_approval_routes_to_remediation():
    state = {
        "approval": {"decision": "approve"}
    }

    assert graph_module.route_after_approval(state) == "remediate"


def test_rejection_routes_to_stop():
    state = {
        "approval": {"decision": "reject"}
    }

    assert graph_module.route_after_approval(state) == "stop"


def test_remediation_is_simulation_only():
    state = {
        "diagnosis": {
            "recommended_action": "Review and simulate rollback"
        }
    }

    result = graph_module.remediate(state)

    assert result["remediation"]["status"] == "simulated_success"
    assert result["remediation"]["executed"] is False
    assert result["remediation"]["action"] == (
        "Review and simulate rollback"
    )


def test_rejection_does_not_execute_remediation():
    state = {
        "diagnosis": {
            "recommended_action": "Review and simulate rollback"
        }
    }

    result = graph_module.stop(state)

    assert result["remediation"]["status"] == "rejected"
    assert result["remediation"]["executed"] is False
    assert "no infrastructure was changed" in (
        result["remediation"]["note"]
    )
