import json
import logging

from capability_bridge.core.observability.logging import ALLOWED_FIELDS, log_call, setup_logging


def test_log_call_whitelist(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="capability_bridge"):
        log_call(
            request_id="r1",
            capability="vision",
            provider="qwen",
            model="qwen3-vl-flash",
            latency_ms=5,
            success=True,
            fallback_count=0,
            secret_prompt="NEVER log me",
            image_bytes="NEVER log me either",
        )
    record = json.loads(caplog.records[-1].getMessage())
    assert set(record.keys()) <= set(ALLOWED_FIELDS)
    assert "NEVER log me" not in caplog.text
    assert record["request_id"] == "r1"
    assert record["success"] is True


def test_setup_logging_installs_handler() -> None:
    setup_logging()
    assert logging.getLogger("capability_bridge").handlers
