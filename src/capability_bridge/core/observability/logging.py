from __future__ import annotations

import json
import logging

#: The ONLY fields a call may log. Anything else is dropped at the gate (privacy).
ALLOWED_FIELDS = (
    "request_id",
    "capability",
    "provider",
    "model",
    "latency_ms",
    "success",
    "error_type",
    "fallback_count",
)


def setup_logging(level: int = logging.INFO) -> None:
    logger = logging.getLogger("capability_bridge")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(level)


def log_call(**fields) -> None:
    record = {key: fields[key] for key in ALLOWED_FIELDS if key in fields}
    logging.getLogger("capability_bridge").info(json.dumps(record, ensure_ascii=False))
