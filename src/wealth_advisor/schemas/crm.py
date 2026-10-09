from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskTolerance = Literal["conservative", "moderate", "aggressive"]
DataQuality = Literal["ok", "degraded"]


class CrmProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    risk_tolerance: RiskTolerance
    goals: list[str] = Field(default_factory=list)
    last_contact: date | None = None
    advisor_notes: str | None = None
    status: DataQuality = Field(
        default="ok",
        description='"degraded" when the CRM tool fell back to a default profile '
        "because the live CRM was unavailable and nothing was cached.",
    )
