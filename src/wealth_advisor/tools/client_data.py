from __future__ import annotations

from pathlib import Path
from typing import Any

from wealth_advisor.schemas.client import ClientProfile
from wealth_advisor.tools.base import BaseTool


class ClientDataTool(BaseTool[ClientProfile]):
    """Loads a client's financial data from data/clients/<client_id>.json. Delegates all
    parsing and validation to ClientProfile.from_file(); execute() converts the
    ClientDataValidationError it raises on bad data into a failed ToolResult, same as
    any other tool failure."""

    name = "client_data_tool"

    def __init__(self, clients_dir: Path) -> None:
        self._clients_dir = clients_dir

    def validate(self, **kwargs: Any) -> None:
        if not kwargs.get("client_id"):
            raise ValueError("client_id is required")

    def _run(self, *, client_id: str, **_: Any) -> ClientProfile:
        path = self._clients_dir / f"{client_id}.json"
        return ClientProfile.from_file(path)
