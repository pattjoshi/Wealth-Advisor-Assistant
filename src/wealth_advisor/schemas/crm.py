from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskTolerance = Literal["conservative", "moderate", "aggressive"]


class CrmProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    risk_tolerance: RiskTolerance
    goals: list[str] = Field(default_factory=list)
    last_contact: date | None = None
    advisor_notes: str | None = None
