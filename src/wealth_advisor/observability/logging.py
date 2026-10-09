from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

# Fields that must never reach a log line, wherever they appear in a nested event dict.
PII_KEYS = {"full_name", "date_of_birth", "payee", "advisor_notes"}


def mask_pii(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor: recursively redacts known PII fields before anything is
    rendered to the console or the log file. Runs on every log call, so a field added
    to a nested dict later is still caught — masking isn't opt-in per call site."""
    return _mask_value(event_dict)


def _mask_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if key in PII_KEYS and val is not None else _mask_value(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    return value


def configure_logging(*, log_level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure structlog for JSON-lines output. Console logs go to stderr (never
    stdout) so the CLI's JSON report on stdout stays a single parseable object."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(format="%(message)s", level=level, handlers=handlers, force=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            mask_pii,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial_values: Any) -> Any:
    return structlog.get_logger(**initial_values)
