import os
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from app.evidence import get_evidence
from app.diagnosis import diagnose


class IncidentState(TypedDict, total=False):
    incident_id: str
    service: str
    environment: str
    evidence: dict[str, Any]
    diagnosis: dict[str, Any]
    llm_explanation: str
    approval: dict[str, Any]
    remediation: dict[str, Any]


def investigate(state: IncidentState) -> dict:
    return {"evidence": get_evidence(state.get("service", "checkout-api"))}


def analyze(state: IncidentState) -> dict:
    return {"diagnosis": diagnose(state["evidence"])}


def optional_llm_explanation(state: IncidentState) -> dict:
    if os.getenv("ENABLE_LLM", "false").lower() != "true":
        return {"llm_explanation": "LLM disabled; using deterministic evidence analysis."}
    try:
        from app.local_llm import explain_with_local_llm
        return {
            "llm_explanation": explain_with_local_llm(
                state["evidence"], state["diagnosis"]
            )
        }
    except Exception as exc:
        # LLM failure must not bypass the approval gate or block deterministic findings.
        return {"llm_explanation": f"Local LLM unavailable ({type(exc).__name__}); deterministic findings retained."}


def approval_gate(state: IncidentState) -> dict:
    decision = interrupt({
        "incident_id": state["incident_id"],
        "diagnosis": state["diagnosis"],
        "llm_explanation": state.get("llm_explanation", ""),
        "proposed_action": state["diagnosis"]["recommended_action"],
        "message": "Review the evidence and explicitly approve or reject the simulated action.",
    })
    return {"approval": decision}


def route_after_approval(state: IncidentState):
    if state.get("approval", {}).get("decision") == "approve":
        return "remediate"
    return "stop"


def remediate(state: IncidentState) -> dict:
    # Safety boundary: simulated only; no shell, Kubernetes, cloud, or deployment calls.
    return {"remediation": {
        "status": "simulated_success",
        "executed": False,
        "action": state["diagnosis"]["recommended_action"],
        "note": "No infrastructure was changed.",
    }}


def stop(state: IncidentState) -> dict:
    return {"remediation": {
        "status": "rejected",
        "executed": False,
        "action": state["diagnosis"]["recommended_action"],
        "note": "Reviewer rejected the proposed action; no infrastructure was changed.",
    }}


builder = StateGraph(IncidentState)
builder.add_node("investigate", investigate)
builder.add_node("analyze", analyze)
builder.add_node("optional_llm_explanation", optional_llm_explanation)
builder.add_node("approval_gate", approval_gate)
builder.add_node("remediate", remediate)
builder.add_node("stop", stop)

builder.add_edge(START, "investigate")
builder.add_edge("investigate", "analyze")
builder.add_edge("analyze", "optional_llm_explanation")
builder.add_edge("optional_llm_explanation", "approval_gate")
builder.add_conditional_edges(
    "approval_gate", route_after_approval,
    {"remediate": "remediate", "stop": "stop"},
)
builder.add_edge("remediate", END)
builder.add_edge("stop", END)

# In-memory checkpoint is acceptable for a single-process lab demo only.
graph = builder.compile(checkpointer=InMemorySaver())
