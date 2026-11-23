from app.diagnosis import diagnose


def test_payment_timeout_is_identified():
    evidence = {
        "service": "checkout-api",
        "logs": [
            {"status_code": 500, "message": "Payment dependency timed out",
             "timestamp": "2026-10-27T09:05:00Z", "release": "v2.4"}
        ],
        "deployments": [{"release": "v2.4", "timestamp": "2026-10-27T09:04:30Z"}],
        "metrics": {"source": "simulated_fixture"},
        "warnings": [],
    }
    result = diagnose(evidence)
    assert "Payment dependency timeouts" in result["likely_root_cause"]
    assert 0 <= result["confidence"] <= 1
    assert result["evidence"]


def test_empty_evidence_does_not_claim_payment_failure():
    result = diagnose({
        "service": "checkout-api", "logs": [], "deployments": [],
        "metrics": {"source": "simulated_fixture"}, "warnings": [],
    })
    assert result["confidence"] < 0.5
    assert "Insufficient evidence" in result["likely_root_cause"]
    assert "do not remediate" in result["recommended_action"]


def test_deployment_timing_is_reported():
    result = diagnose({
        "service": "checkout-api",
        "logs": [{"status_code": 500, "message": "Payment dependency timed out",
                  "timestamp": "2026-10-27T09:05:00Z", "release": "v2.4"}],
        "deployments": [{"release": "v2.4", "timestamp": "2026-10-27T09:04:30Z"}],
        "metrics": {"source": "simulated_fixture"}, "warnings": [],
    })
    assert "1 errors have timestamps" in result["evidence"][2]["observation"]


def test_http_5xx_without_payment_timeouts():
    from app.diagnosis import diagnose

    evidence = {
        "service": "checkout-api",
        "logs": [
            {
                "status_code": 500,
                "message": "Internal server error",
                "timestamp": "2026-11-22T10:00:00",
                "release": "2.4",
            }
        ],
        "deployments": [
            {
                "release": "2.4",
                "timestamp": "2026-11-22T09:00:00",
            }
        ],
        "metrics": {"source": "simulated_fixture"},
        "warnings": [],
    }

    result = diagnose(evidence)

    assert result["confidence"] == 0.42
    assert "immediate cause is unconfirmed" in result["likely_root_cause"]
    assert result["recommended_action"] == (
        "Collect dependency and application telemetry before remediation"
    )
    assert result["error_releases"] == ["2.4"]
