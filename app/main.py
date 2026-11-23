
from contextlib import asynccontextmanager
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from langgraph.types import Command
from prometheus_client import Counter, Histogram, make_asgi_app

from app.audit import initialize, record, get_events
from app.graph import graph
from app.schemas import IncidentRequest, ApprovalRequest
from app.security import action_digest, verify_action_digest


INCIDENTS_STARTED = Counter(
    "copilot_incidents_started_total",
    "Incident investigations started",
)

APPROVALS = Counter(
    "copilot_approval_decisions_total",
    "Approval decisions",
    ["decision"],
)

INVESTIGATION_DURATION = Histogram(
    "copilot_investigation_duration_seconds",
    "Investigation graph duration",
)

REMEDIATION_RESULTS = Counter(
    "copilot_remediation_results_total",
    "Simulated remediation outcomes",
    ["status"],
)


# Single-process local research implementation.
pending: dict[str, dict] = {}
pending_lock = Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield


app = FastAPI(
    title="Agentic AI Incident Copilot",
    description=(
        "Local lab: evidence-driven incident analysis "
        "with human approval and simulated remediation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/metrics", make_asgi_app())


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "remediation_mode": "simulation_only",
    }


@app.post("/incidents")
def create_incident(request: IncidentRequest):
    incident_id = request.incident_id or f"INC-{uuid4()}"
    thread_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    # Register the incident before starting investigation.
    with pending_lock:
        if incident_id in pending:
            raise HTTPException(
                409,
                "This incident ID already has a pending approval.",
            )

        pending[incident_id] = {
            "thread_id": thread_id,
            "config": config,
            "status": "pending",
        }

    INCIDENTS_STARTED.inc()

    record(
        incident_id,
        "investigation_started",
        "system",
        {
            "service": request.service,
            "environment": request.environment,
        },
    )

    try:
        with INVESTIGATION_DURATION.time():
            result = graph.invoke(
                {
                    "incident_id": incident_id,
                    "service": request.service,
                    "environment": request.environment,
                },
                config=config,
            )

    except Exception as exc:
        with pending_lock:
            pending.pop(incident_id, None)

        record(
            incident_id,
            "investigation_error",
            "system",
            {"error_type": type(exc).__name__},
        )

        raise HTTPException(
            500,
            "Investigation failed; inspect local application logs.",
        ) from exc

    interrupts = result.get("__interrupt__", ())

    if not interrupts:
        with pending_lock:
            pending.pop(incident_id, None)

        raise HTTPException(
            500,
            "Workflow did not pause for human approval.",
        )

    approval_request = interrupts[0].value

    # Read the checkpoint and verify the proposed action.
    snapshot = graph.get_state(config)
    checkpoint_values = snapshot.values

    proposed_action = approval_request["proposed_action"]

    checkpoint_action = (
        checkpoint_values.get("diagnosis", {}).get(
            "recommended_action"
        )
    )

    if (
        checkpoint_values.get("incident_id") != incident_id
        or checkpoint_action != proposed_action
    ):
        with pending_lock:
            pending.pop(incident_id, None)

        record(
            incident_id,
            "action_integrity_check",
            "system",
            {
                "valid": False,
                "stage": "initial_capture",
            },
        )

        raise HTTPException(
            409,
            "Incident or proposed action failed integrity validation.",
        )

    # Bind the incident ID and proposed action using HMAC.
    digest = action_digest(
        incident_id,
        proposed_action,
    )

    with pending_lock:
        context = pending.get(incident_id)

        if context is None:
            raise HTTPException(
                409,
                "Pending approval context was lost.",
            )

        context["proposed_action"] = proposed_action
        context["action_digest"] = digest

    record(
        incident_id,
        "approval_requested",
        "agent",
        {
            "action": proposed_action,
            "confidence": approval_request["diagnosis"]["confidence"],
            "action_digest": digest,
        },
    )

    return {
        "incident_id": incident_id,
        "status": "awaiting_approval",
        "approval_request": approval_request,
    }


@app.post("/incidents/{incident_id}/approval")
def approve_incident(
    incident_id: str,
    request: ApprovalRequest,
):
    # Atomically claim the approval.
    with pending_lock:
        context = pending.get(incident_id)

        if not context:
            raise HTTPException(
                404,
                "No pending approval found for this incident.",
            )

        if context.get("status") != "pending":
            raise HTTPException(
                409,
                "Approval is already being processed or has failed.",
            )

        context["status"] = "processing"

    # Verify the checkpoint against the original action.
    try:
        snapshot = graph.get_state(context["config"])
        checkpoint_values = snapshot.values

        current_action = (
            checkpoint_values.get("diagnosis", {}).get(
                "recommended_action"
            )
        )

        valid_incident = (
            checkpoint_values.get("incident_id") == incident_id
        )

        expected_digest = context.get("action_digest", "")

        valid_action = (
            current_action is not None
            and current_action == context.get("proposed_action")
            and verify_action_digest(
                incident_id,
                current_action,
                expected_digest,
            )
        )

        if not valid_incident or not valid_action:
            raise ValueError(
                "Incident or action integrity verification failed."
            )

    except Exception as exc:
        with pending_lock:
            context["status"] = "failed"

        record(
            incident_id,
            "action_integrity_check",
            "system",
            {
                "valid": False,
                "error_type": type(exc).__name__,
            },
        )

        raise HTTPException(
            409,
            "Approval rejected: action integrity verification failed.",
        ) from exc

    record(
        incident_id,
        "action_integrity_check",
        "system",
        {
            "valid": True,
            "action_digest": expected_digest,
        },
    )

    decision = {
        "decision": request.decision,
        "reviewer": request.reviewer,
        "reason": request.reason,
    }

    try:
        APPROVALS.labels(
            decision=request.decision
        ).inc()

        record(
            incident_id,
            "approval_decision",
            request.reviewer,
            decision,
        )

        # Resume only after successful integrity verification.
        result = graph.invoke(
            Command(resume=decision),
            config=context["config"],
        )

    except Exception as exc:
        with pending_lock:
            context["status"] = "failed"

        record(
            incident_id,
            "resume_error",
            "system",
            {"error_type": type(exc).__name__},
        )

        raise HTTPException(
            500,
            "Could not resume workflow; inspect local application logs.",
        ) from exc

    with pending_lock:
        pending.pop(incident_id, None)

    remediation = result.get(
        "remediation",
        {
            "status": "unknown",
            "executed": False,
        },
    )

    REMEDIATION_RESULTS.labels(
        status=remediation["status"]
    ).inc()

    record(
        incident_id,
        "remediation_result",
        "system",
        remediation,
    )

    return {
        "incident_id": incident_id,
        "status": remediation["status"],
        "result": remediation,
    }


@app.get("/incidents/{incident_id}/audit")
def incident_audit(incident_id: str):
    return {
        "incident_id": incident_id,
        "events": get_events(incident_id),
    }
