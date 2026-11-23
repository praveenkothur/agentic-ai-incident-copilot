# Agentic AI Incident Copilot

A local-first incident investigation lab built with Python, LangGraph, FastAPI, Ollama, Prometheus, Grafana, SQLite, and pytest.

## What it does

- Reads simulated application logs and deployment history.
- Correlates HTTP 5xx errors, payment timeouts, and deployment timestamps.
- Uses LangGraph to investigate, diagnose, and pause for human approval.
- Optionally uses a local Ollama model to explain findings.
- Requires a reviewer decision before the simulated remediation step.
- Records audit events in SQLite.
- Exposes Prometheus metrics and a FastAPI REST interface.
- Includes automated tests for diagnosis, API behavior, approval, and metrics.

## Safety boundary

This repository does not execute production actions. The remediation node only records a simulated outcome. Do not connect it to a real cluster or cloud account without a separate security review, authenticated approvals, durable state, least-privilege credentials, idempotency, and explicit change controls.

The starter implementation uses an in-memory LangGraph checkpointer and an in-process pending-incident dictionary. Restarting the API loses pending workflows. This is for a single-process local lab only.

## Prerequisites

- Windows 10/11 with PowerShell
- Python 3.12
- Git
- Docker Desktop with Docker Compose
- Ollama (optional for deterministic mode; required for local LLM mode)

## 1. Create and activate the virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell session, then activate again.

## 2. Start the local LLM (optional)

Install Ollama from https://ollama.com/download/windows, then:

```powershell
ollama pull qwen2.5:3b
ollama list
```

Keep `ENABLE_LLM=false` for the first run. When the deterministic workflow passes tests, set `ENABLE_LLM=true` in `.env`, then restart the API. The local model is optional and is not used to authorize remediation.

## 3. Start the monitoring services

From the repository root:

```powershell
docker compose up -d
docker compose ps
```

Prometheus: http://localhost:9090/targets  
Grafana: http://localhost:3000

In Grafana, add a Prometheus data source with URL `http://prometheus:9090`. On a fresh local Grafana installation, the default login is commonly `admin` / `admin`; change it immediately.

## 4. Start the API

Open a second PowerShell window, navigate to the repository, and activate the venv:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs  
Health: http://127.0.0.1:8000/health  
Metrics: http://127.0.0.1:8000/metrics

## 5. Run an incident

In Swagger UI, call `POST /incidents`:

```json
{
  "incident_id": "INC-DEMO-001",
  "service": "checkout-api",
  "environment": "production"
}
```

The response should be `awaiting_approval` with a diagnosis and proposed action.

Then call `POST /incidents/INC-DEMO-001/approval`:

```json
{
  "decision": "reject",
  "reviewer": "demo-operator",
  "reason": "Rejecting to test the safe path"
}
```

Expected result: `rejected`, with `executed: false`.

Run a new incident ID to test approval:

```json
{
  "incident_id": "INC-DEMO-002",
  "service": "checkout-api",
  "environment": "production"
}
```

Then approve it:

```json
{
  "decision": "approve",
  "reviewer": "demo-operator",
  "reason": "Approved for simulation testing only"
}
```

Expected result: `simulated_success`, with `executed: false`. No infrastructure changes occur.

Inspect audit events at:
`GET /incidents/INC-DEMO-002/audit`

## 6. Run tests

```powershell
pytest -v
pytest --cov=app --cov-report=term-missing
```

## Prometheus metrics

The API exposes:
- `copilot_incidents_started_total`
- `copilot_approval_decisions_total`
- `copilot_investigation_duration_seconds`
- `copilot_remediation_results_total`

The fixture-based incident metrics are separate from checkout application metrics. To query live application error rates, instrument a test application to export `checkout_http_requests_total` with a `status` label; otherwise Prometheus will correctly return no matching series.

## Troubleshooting

- If `ollama` is not recognized, reopen PowerShell after installing Ollama.
- If the LLM is slow, keep `ENABLE_LLM=false`; deterministic analysis still works.
- If Prometheus target is down, confirm the API is running on port 8000 and `/metrics` returns text.
- If Docker cannot pull images, check Docker Desktop and network connectivity.
- Do not restart Uvicorn between starting an incident and submitting its approval; the demo uses in-memory workflow state.
- If a port is already in use, stop the conflicting service or change the published port in `docker-compose.yml`.

## Next improvements

1. Replace in-memory graph state with a persistent LangGraph checkpointer.
2. Store pending incidents in a durable database.
3. Add authenticated reviewer identities and authorization.
4. Add a dedicated simulated checkout service that exports metrics.
5. Add evidence-grounding validation for every LLM claim.
6. Add an Azure Monitor evidence adapter after the local lab is stable.
