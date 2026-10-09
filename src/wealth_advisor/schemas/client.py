from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wealth_advisor.errors import ClientDataValidationError

AssetClass = Literal["equity", "bond", "cash", "real_estate", "commodity", "other"]
AccountType = Literal["brokerage", "retirement", "checking", "savings"]
TransactionType = Literal["debit", "credit", "transfer_in", "transfer_out", "withdrawal", "deposit"]


class Holding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    asset_class: AssetClass
    sector: str | None = None
    quantity: float = Field(ge=0)
    value: float = Field(ge=0)


class Account(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    account_type: AccountType
    balance: float
    holdings: list[Holding] = Field(default_factory=list)


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    date: date
    amount: float
    category: str
    payee: str | None = None
    type: TransactionType


class ClientProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    full_name: str
    date_of_birth: date | None = None
    base_currency: str = "USD"
    accounts: list[Account] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> ClientProfile:
        """Load and validate a client JSON file, raising ClientDataValidationError with a
        readable, field-level message on bad JSON or a schema mismatch — never a raw
        traceback."""
        try:
            raw = json.loads(path.read_text())
        except OSError as exc:
            raise ClientDataValidationError(str(path), f"could not read file: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ClientDataValidationError(str(path), f"invalid JSON: {exc}") from exc

        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise ClientDataValidationError(str(path), _format_validation_error(exc)) from exc


def _format_validation_error(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        field_path = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"{field_path}: {error['msg']}")
    return "; ".join(lines)
