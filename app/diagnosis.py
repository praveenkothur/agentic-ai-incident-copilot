from typing import Any


def diagnose(evidence: dict[str, Any]) -> dict[str, Any]:
    logs = evidence.get("logs", [])
    deployments = sorted(
        evidence.get("deployments", []),
        key=lambda item: item.get("timestamp", ""),
    )
    errors = [x for x in logs if int(x.get("status_code", 0)) >= 500]
    timeouts = [
        x for x in logs
        if "timeout" in x.get("message", "").lower()
        or "timed out" in x.get("message", "").lower()
    ]
    latest_release = deployments[-1].get("release", "unknown") if deployments else "unknown"

    error_releases = {x.get("release") for x in errors}
    latest_deploy_time = deployments[-1].get("timestamp") if deployments else None
    errors_after_latest_deploy = [
        x for x in errors
        if latest_deploy_time and x.get("timestamp", "") >= latest_deploy_time
    ]

    if errors and timeouts:
        cause = (
            "Payment dependency timeouts are the observed failure mechanism. "
            "The latest deployment may be a trigger, but the supplied evidence "
            "does not prove causation."
        )
        confidence = 0.78 if errors_after_latest_deploy else 0.62
        action = "Review and simulate rollback to the previous known-good release"
    elif errors:
        cause = "HTTP 5xx responses were observed, but the immediate cause is unconfirmed."
        confidence = 0.42
        action = "Collect dependency and application telemetry before remediation"
    else:
        cause = "Insufficient evidence to identify an active failure."
        confidence = 0.15
        action = "Continue investigation; do not remediate"

    evidence_items = [
        {
            "source": "application_logs",
            "observation": f"{len(logs)} log records inspected; {len(errors)} HTTP 5xx responses found.",
        },
        {
            "source": "dependency_logs",
            "observation": f"{len(timeouts)} payment timeout records found.",
        },
        {
            "source": "deployment_history",
            "observation": (
                f"Latest release is {latest_release}; "
                f"{len(errors_after_latest_deploy)} errors have timestamps at or after its deployment."
            ),
        },
        {
            "source": "metrics",
            "observation": f"Metrics source: {evidence.get('metrics', {}).get('source', 'unknown')}.",
        },
    ]

    return {
        "summary": f"Investigated {len(logs)} log records for {evidence.get('service', 'unknown service')}.",
        "likely_root_cause": cause,
        "confidence": confidence,
        "evidence": evidence_items,
        "alternative_hypotheses": [
            "Payment API degradation unrelated to the release",
            "Configuration or timeout change in the latest release",
            "Network connectivity issue between checkout and payment",
        ],
        "recommended_action": action,
        "risk": (
            "A real rollback can cause compatibility or data issues. "
            "Validate release compatibility and obtain change approval before any production action."
        ),
        "latest_release": latest_release,
        "error_releases": sorted(str(x) for x in error_releases if x is not None),
        "warnings": evidence.get("warnings", []),
    }
