import json
from pathlib import Path

OUTPUT = Path("experiments/dataset/diagnosis/development_scenarios.json")

PAYMENT = "payment_timeout"
HTTP5XX = "http_5xx"
INSUFFICIENT = "insufficient_evidence"

ACTIONS = {
    PAYMENT: "Review and simulate rollback to the previous known-good release",
    HTTP5XX: "Collect dependency and application telemetry before remediation",
    INSUFFICIENT: "Continue investigation; do not remediate",
}

cases = [
    # 1-6: Explicit payment timeout evidence
    ("DEV-PAY-001", PAYMENT, 500, "Payment API request timeout", "payment", True, "Explicit payment timeout with HTTP 500."),
    ("DEV-PAY-002", PAYMENT, 502, "Payment dependency timed out", "payment", True, "Payment timeout with HTTP 502."),
    ("DEV-PAY-003", PAYMENT, 503, "Payment service request timed out", "checkout", True, "Payment timeout appears in message despite checkout service name."),
    ("DEV-PAY-004", PAYMENT, 500, "Request timed out while calling payment gateway", "checkout", False, "Explicit payment timeout without deployment history."),
    ("DEV-PAY-005", PAYMENT, 504, "Payment authorization timeout", "payment", True, "Payment-specific timeout with HTTP 504."),
    ("DEV-PAY-006", PAYMENT, 500, "Payment processing timed out after retry", "payment", True, "Payment timeout after retry."),

    # 7-12: Generic HTTP 5xx without explicit payment evidence
    ("DEV-HTTP-001", HTTP5XX, 500, "Internal server error", "checkout", True, "HTTP 500 without dependency-specific evidence."),
    ("DEV-HTTP-002", HTTP5XX, 502, "Bad gateway response", "gateway", True, "HTTP 502 without payment timeout evidence."),
    ("DEV-HTTP-003", HTTP5XX, 503, "Service temporarily unavailable", "checkout", False, "HTTP 503 without deployment history."),
    ("DEV-HTTP-004", HTTP5XX, 504, "Gateway timeout response", "gateway", True, "Generic gateway timeout must not be treated as payment timeout."),
    ("DEV-HTTP-005", HTTP5XX, 500, "Unhandled application exception", "checkout", True, "Application exception with no dependency evidence."),
    ("DEV-HTTP-006", HTTP5XX, 502, "Upstream connection failure", "inventory", False, "Upstream failure without explicit payment evidence."),

    # 13-18: Insufficient evidence
    ("DEV-INS-001", INSUFFICIENT, None, None, None, False, "No logs or deployment evidence."),
    ("DEV-INS-002", INSUFFICIENT, 200, "Request completed successfully", "checkout", True, "Only successful request evidence."),
    ("DEV-INS-003", INSUFFICIENT, 404, "Resource not found", "catalog", True, "HTTP 4xx is not an HTTP 5xx failure."),
    ("DEV-INS-004", INSUFFICIENT, None, None, None, False, "Metrics and warnings exist but no error logs."),
    ("DEV-INS-005", INSUFFICIENT, 400, "Invalid request payload", "checkout", False, "Client-side HTTP 400 without server error evidence."),
    ("DEV-INS-006", INSUFFICIENT, None, None, None, True, "Deployment exists but no failure evidence."),

    # 19-22: Conflicting evidence. Conservative expected labels.
    ("DEV-CON-001", HTTP5XX, 500, "Payment service returned an error; timeout not confirmed", "payment", True, "Payment-related service name alone does not establish a timeout."),
    ("DEV-CON-002", HTTP5XX, 503, "Payment service unavailable", "payment", True, "Payment service failure without explicit timeout evidence."),
    ("DEV-CON-003", HTTP5XX, 500, "Internal server error after payment success", "checkout", True, "Payment success conflicts with an unclassified application error."),
    ("DEV-CON-004", HTTP5XX, 502, "Upstream failure; dependency identity unknown", "gateway", False, "Dependency identity and failure mechanism are unconfirmed."),

    # 23-26: Gateway timeout boundary cases
    ("DEV-GW-001", HTTP5XX, 504, "Gateway timeout response", "gateway", True, "Generic gateway timeout is not explicit payment evidence."),
    ("DEV-GW-002", HTTP5XX, 504, "Upstream request timed out", "gateway", True, "Generic upstream timeout without payment context."),
    ("DEV-GW-003", HTTP5XX, 504, "Load balancer timeout", "gateway", False, "Load balancer timeout without payment evidence."),
    ("DEV-GW-004", HTTP5XX, 504, "Checkout request exceeded gateway timeout", "checkout", True, "Checkout gateway timeout without payment dependency evidence."),

    # 27-30: Deployment and timestamp inconsistencies
    ("DEV-DEP-001", PAYMENT, 500, "Payment API request timeout", "payment", True, "Explicit payment timeout; deployment timestamp ordering requires scrutiny."),
    ("DEV-DEP-002", PAYMENT, 502, "Payment dependency timed out", "payment", False, "Explicit payment timeout with no deployment records."),
    ("DEV-DEP-003", HTTP5XX, 500, "Internal server error", "checkout", True, "HTTP 5xx with inconsistent deployment timing and no payment timeout."),
    ("DEV-DEP-004", HTTP5XX, 503, "Service unavailable", "checkout", True, "HTTP 5xx where deployment evidence does not establish causality."),
]

def build_evidence(item, index):
    scenario_id, expected, status, message, service, has_deployment, rationale = item

    logs = []
    if status is not None:
        logs.append({
            "timestamp": f"2026-10-{(index % 28) + 1:02d}T10:00:00Z",
            "status_code": status,
            "message": message,
            "service": service,
            "release": "2.4",
        })

    deployments = []
    if has_deployment:
        deployments = [
            {"timestamp": "2026-10-01T09:00:00Z", "release": "2.3"},
            {"timestamp": "2026-10-01T10:00:00Z", "release": "2.4"},
        ]

    metrics = {
        "http_5xx_rate": 0.08 if status and status >= 500 else 0.0,
        "request_count": 100,
    }

    warnings = []
    if "inconsistent" in rationale.lower():
        warnings.append("Deployment timing is inconsistent or insufficient to establish causality.")

    if "conflict" in rationale.lower() or scenario_id.startswith("DEV-CON"):
        warnings.append("Evidence may support multiple interpretations.")

    return {
        "scenario_id": scenario_id,
        "expected_class": expected,
        "expected_recommended_action": ACTIONS[expected],
        "evidence": {
            "service": "checkout",
            "logs": logs,
            "deployments": deployments,
            "metrics": metrics,
            "warnings": warnings,
        },
        "rationale": rationale,
        "label_provenance": "Researcher-assigned synthetic development label; requires independent review.",
        "dataset_version": "1.0",
    }

dataset = [build_evidence(item, i) for i, item in enumerate(cases, start=1)]

# Add genuine timestamp-ordering boundary cases.
by_id = {item["scenario_id"]: item for item in dataset}

# Deployment 2.4 occurs after the incident log timestamp.
by_id["DEV-DEP-001"]["evidence"]["deployments"] = [
    {"timestamp": "2026-10-27T09:00:00Z", "release": "2.3"},
    {"timestamp": "2026-10-29T10:00:00Z", "release": "2.4"},
]
by_id["DEV-DEP-001"]["evidence"]["warnings"] = [
    "Latest deployment timestamp is later than the observed incident."
]

# Both recorded deployments occur after the incident log timestamp.
by_id["DEV-DEP-003"]["evidence"]["deployments"] = [
    {"timestamp": "2026-10-03T09:00:00Z", "release": "2.3"},
    {"timestamp": "2026-10-04T10:00:00Z", "release": "2.4"},
]
by_id["DEV-DEP-003"]["evidence"]["warnings"] = [
    "Deployment records occur after the observed incident timestamp."
]

# This case must contain actual warning evidence.
by_id["DEV-INS-004"]["evidence"]["warnings"] = [
    "Elevated latency reported, but no HTTP 5xx log records are available."
]


assert len(dataset) == 30
assert len({x["scenario_id"] for x in dataset}) == 30
assert all(x["expected_class"] in ACTIONS for x in dataset)
assert all(x["expected_recommended_action"] == ACTIONS[x["expected_class"]] for x in dataset)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

print(f"Created: {OUTPUT}")
print(f"Total scenarios: {len(dataset)}")

for label in ACTIONS:
    count = sum(x["expected_class"] == label for x in dataset)
    print(f"{label}: {count}")

print("Schema and duplicate-ID checks: PASSED")
