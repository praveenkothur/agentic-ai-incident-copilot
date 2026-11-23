
import re


def _has_confirmed_payment_timeout(log):
    message = log.get("message", "").lower()
    service = log.get("service", "").lower()

    has_timeout = (
        "timeout" in message or "timed out" in message
    )
    has_payment = (
        "payment" in message or "payment" in service
    )

    if not (has_timeout and has_payment):
        return False

    negated_timeout = re.search(
        r"\b(?:timeout|timed out)\s+"
        r"(?:(?:is|was|has been)\s+)?"
        r"(?:not|never)\s+"
        r"(?:confirmed|observed|detected|reported|established)\b",
        message,
    )

    explicit_absence = re.search(
        r"\b(?:no|without)\s+(?:explicit\s+)?"
        r"(?:payment\s+)?(?:dependency\s+)?"
        r"(?:request\s+)?(?:timeout|timed out)\b",
        message,
    )

    not_a_timeout = re.search(
        r"\b(?:not|never)\s+(?:a\s+)?"
        r"(?:payment\s+)?(?:dependency\s+)?"
        r"(?:request\s+)?(?:timeout|timed out)\b",
        message,
    )

    return not (
        negated_timeout or explicit_absence or not_a_timeout
    )


def diagnose(evidence):
    logs = evidence.get("logs", [])
    deployments = sorted(
        evidence.get("deployments", []),
        key=lambda x: x.get("timestamp", ""),
    )

    errors = [
        log for log in logs
        if int(log.get("status_code", 0)) >= 500
    ]

    # Require explicit payment-related timeout evidence.
    # Negated or unconfirmed timeout statements are excluded.
    payment_timeouts = [
        log for log in logs
        if _has_confirmed_payment_timeout(log)
    ]

    errors_with_timestamps = [
        log for log in errors if log.get("timestamp")
    ]

    latest_release = deployments[-1] if deployments else None

    latest_release_name = (
        latest_release.get("release") if latest_release else None
    )

    error_releases = sorted({
        log.get("release")
        for log in errors
        if log.get("release")
    })

    warnings = evidence.get("warnings", [])

    if errors and payment_timeouts:
        confidence = 0.78 if latest_release_name else 0.62

        return {
            "likely_root_cause": (
                "Payment dependency timeouts are the observed failure mechanism."
            ),
            "confidence": confidence,
            "evidence": [
                {
                    "observation": (
                        f"{len(payment_timeouts)} payment timeout records found."
                    )
                },
                {
                    "observation": (
                        f"{len(errors)} HTTP 5xx errors found."
                    )
                },
                {
                    "observation": (
                        f"{len(errors_with_timestamps)} errors have timestamps."
                    )
                },
            ],
            "alternative_hypotheses": [
                "Configuration or timeout change in the latest release",
                "Transient payment dependency failure",
            ],
            "recommended_action": (
                "Review and simulate rollback to the previous known-good release"
            ),
            "risk": "high",
            "latest_release": latest_release_name,
            "error_releases": error_releases,
            "warnings": warnings,
        }

    if errors:
        return {
            "likely_root_cause": (
                "HTTP 5xx errors detected; immediate cause is unconfirmed."
            ),
            "confidence": 0.42,
            "evidence": [
                {
                    "observation": f"{len(errors)} HTTP 5xx errors found."
                },
                {
                    "observation": (
                        "No explicit payment dependency timeout evidence found."
                    )
                },
                {
                    "observation": (
                        f"{len(errors_with_timestamps)} errors have timestamps."
                    )
                },
            ],
            "alternative_hypotheses": [
                "Application exception",
                "Gateway or upstream service failure",
                "Dependency latency or connectivity issue",
            ],
            "recommended_action": (
                "Collect dependency and application telemetry before remediation"
            ),
            "risk": "medium",
            "latest_release": latest_release_name,
            "error_releases": error_releases,
            "warnings": warnings,
        }

    return {
        "likely_root_cause": "Insufficient evidence to identify a failure.",
        "confidence": 0.15,
        "evidence": [
            {
                "observation": "No HTTP 5xx records found."
            }
        ],
        "alternative_hypotheses": [
            "Insufficient application telemetry",
            "Intermittent or unobserved failure",
        ],
        "recommended_action": "Continue investigation; do not remediate",
        "risk": "low",
        "latest_release": latest_release_name,
        "error_releases": error_releases,
        "warnings": warnings,
    }
