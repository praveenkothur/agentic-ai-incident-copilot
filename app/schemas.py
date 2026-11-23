from typing import Literal
from pydantic import BaseModel, Field


class IncidentRequest(BaseModel):
    incident_id: str = Field(default="INC-DEMO-001", min_length=3, max_length=100)
    service: str = Field(default="checkout-api", min_length=1, max_length=100)
    environment: str = Field(default="production", min_length=1, max_length=50)


class ApprovalRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=3, max_length=500)
