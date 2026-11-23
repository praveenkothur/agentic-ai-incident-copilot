import json
import os
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def _read_json(filename: str) -> list[dict[str, Any]]:
    with (DATA_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def get_evidence(service: str) -> dict[str, Any]:
    logs = [x for x in _read_json("logs.json") if x.get("service") == service]
    deployments = [
        x for x in _read_json("deployments.json") if x.get("service") == service
    ]

    result: dict[str, Any] = {
        "service": service,
        "logs": logs,
        "deployments": deployments,
        "metrics": {"source": "simulated_fixture", "http_5xx_rate": None},
        "dependency": {"name": "payment-api", "observed_timeouts": 0},
        "warnings": [],
    }

    result["dependency"]["observed_timeouts"] = sum(
        1 for item in logs if "timeout" in item.get("message", "").lower()
        or "timed out" in item.get("message", "").lower()
    )

    prometheus_url = os.getenv("PROMETHEUS_URL", "").strip()
    if prometheus_url:
        try:
            response = requests.get(
                f"{prometheus_url.rstrip('/')}/api/v1/query",
                params={"query": 'sum(rate(checkout_http_requests_total{status=~"5.."}[5m]))'},
                timeout=2,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") == "success":
                result["metrics"] = {
                    "source": "prometheus",
                    "http_5xx_rate": payload.get("data", {}).get("result", []),
                }
            else:
                result["warnings"].append("Prometheus returned a non-success response.")
        except requests.RequestException as exc:
            result["warnings"].append(
                f"Prometheus unavailable; using fixture evidence ({type(exc).__name__})."
            )

    return result
