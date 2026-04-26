import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from fastapi.testclient import TestClient

import middleware.app as app_module
from middleware.file_ingest import stream_jsonl
from middleware.logging_config import configure_logging, redact_text
from middleware.pishock import BeepOnlyPiShockClient, DryRunPiShockClient
from middleware.runtime_mode import RuntimeMode
from middleware.security import compute_signature


class FakeOperateClient:
    def __init__(self):
        self.calls: list[tuple[int, int, int]] = []

    async def operate(self, op: int, intensity: int, duration_s: int) -> tuple[int, str]:
        self.calls.append((op, intensity, duration_s))
        return 200, "ok"


class _CleanupHandle(Protocol):
    name: str

    def cleanup(self) -> None:
        pass


def _temp_log_path() -> tuple[_CleanupHandle, Path]:
    base = Path(".tmp_test_logging")
    base.mkdir(parents=True, exist_ok=True)
    path = base / next(tempfile._get_candidate_names())
    path.mkdir(parents=True, exist_ok=True)

    class _Cleanup:
        name = str(path)

        def cleanup(self) -> None:
            shutil.rmtree(path, ignore_errors=True)

    return _Cleanup(), path / "logs" / "middleware.log"


def test_redaction_filter_masks_secrets() -> None:
    text = redact_text(
        'username="operator" api_key=abc123 share_code=share-value hmac_secret=hm secret=value '
        'token=t Authorization=Bearer abc.def X-Signature=sha256=abc '
        '{"api_key":"json-secret"}'
    )

    assert "[REDACTED]" in text
    for leaked in ("operator", "abc123", "share-value", "json-secret", "Bearer abc.def", "sha256=abc"):
        assert leaked not in text


def test_logs_directory_and_file_creation_works() -> None:
    temp_dir, log_path = _temp_log_path()
    try:
        configure_logging(log_path, force=True)
        logging.getLogger("middleware.tests").info("hello")

        assert log_path.exists()
        assert "hello" in log_path.read_text(encoding="utf-8")
    finally:
        temp_dir.cleanup()


def test_startup_logging_does_not_expose_secrets(monkeypatch) -> None:
    temp_dir, log_path = _temp_log_path()
    try:
        configure_logging(log_path, force=True)
        monkeypatch.setattr(
            app_module._config,
            "pishock",
            {
                "dry_run": True,
                "username": "real-user",
                "api_key": "real-api-key",
                "share_code": "real-share-code",
            },
        )

        app_module._log_startup_info()

        log_text = log_path.read_text(encoding="utf-8")
        assert "app started" in log_text
        assert "real-user" not in log_text
        assert "real-api-key" not in log_text
        assert "real-share-code" not in log_text
    finally:
        temp_dir.cleanup()


def test_event_rejection_logs_reason_without_signature_or_secret() -> None:
    temp_dir, log_path = _temp_log_path()
    try:
        configure_logging(log_path, force=True)
        client = TestClient(app_module.app)

        res = client.post(
            "/event",
            content=b'{"event_type":"player_healed"}',
            headers={"x-signature": "sha256=do-not-log-this", "content-type": "application/json"},
        )

        assert res.status_code == 401
        log_text = log_path.read_text(encoding="utf-8")
        assert "invalid_signature" in log_text
        assert "do-not-log-this" not in log_text
        assert app_module._config.hmac_secret not in log_text
    finally:
        temp_dir.cleanup()


def test_event_policy_failure_response_does_not_expose_secret(monkeypatch) -> None:
    temp_dir, log_path = _temp_log_path()
    secret_value = "policy-secret-value"
    try:
        configure_logging(log_path, force=True)
        app_module._sessions_armed["abc"] = True

        def fail_policy(*_args, **_kwargs):
            raise RuntimeError(f"api_key={secret_value}")

        monkeypatch.setattr(app_module._policy, "evaluate", fail_policy)
        payload = {
            "event_type": "player_healed",
            "ts_ms": 1,
            "session_id": "abc",
            "armed": True,
            "context": {},
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        sig = compute_signature(app_module._config.hmac_secret, body)

        res = TestClient(app_module.app).post(
            "/event",
            content=body,
            headers={"x-signature": sig, "content-type": "application/json"},
        )

        assert res.status_code == 200
        response_text = res.text
        assert secret_value not in response_text
        assert res.json() == {
            "accepted": False,
            "reason": "policy_evaluation_failed",
            "error_code": "policy_evaluation_failed",
        }
        log_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in log_text
        assert "api_key=[REDACTED]" in log_text
    finally:
        app_module._sessions_armed.clear()
        temp_dir.cleanup()


def test_event_pishock_failure_response_does_not_expose_secret(monkeypatch) -> None:
    temp_dir, log_path = _temp_log_path()
    secret_value = "device-secret-value"
    try:
        configure_logging(log_path, force=True)
        app_module._sessions_armed["abc"] = True
        monkeypatch.setattr(app_module._config, "pishock", {**app_module._config.pishock, "dry_run": False})
        monkeypatch.setattr(app_module, "_runtime_mode", RuntimeMode.LIVE)

        async def fail_operate(*_args, **_kwargs):
            raise RuntimeError(f"share_code={secret_value}")

        monkeypatch.setattr(app_module._client, "operate", fail_operate)
        payload = {
            "event_type": "player_healed",
            "ts_ms": 1,
            "session_id": "abc",
            "armed": True,
            "context": {},
        }
        body = json.dumps(payload, separators=(",", ":")).encode()
        sig = compute_signature(app_module._config.hmac_secret, body)

        res = TestClient(app_module.app).post(
            "/event",
            content=body,
            headers={"x-signature": sig, "content-type": "application/json"},
        )

        assert res.status_code == 200
        response_text = res.text
        assert secret_value not in response_text
        assert res.json() == {
            "accepted": False,
            "reason": "pishock_operate_failed",
            "error_code": "pishock_operate_failed",
        }
        log_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in log_text
        assert "share_code=[REDACTED]" in log_text
    finally:
        app_module._sessions_armed.clear()
        temp_dir.cleanup()


def test_test_mode_logs_dry_run_no_real_api() -> None:
    temp_dir, log_path = _temp_log_path()
    try:
        configure_logging(log_path, force=True)
        client = DryRunPiShockClient()

        asyncio.run(client.operate(op=1, intensity=5, duration_s=1))

        log_text = log_path.read_text(encoding="utf-8")
        assert "dry-run operation" in log_text
        assert "no_real_api=true" in log_text
    finally:
        temp_dir.cleanup()


def test_beep_mode_logs_vibrate_and_shock_blocks() -> None:
    temp_dir, log_path = _temp_log_path()
    try:
        configure_logging(log_path, force=True)
        fake = FakeOperateClient()
        client = BeepOnlyPiShockClient(fake)

        for op in (1, 0):
            try:
                asyncio.run(client.operate(op=op, intensity=1, duration_s=1))
                raise AssertionError("expected runtime mode block")
            except RuntimeError:
                pass

        log_text = log_path.read_text(encoding="utf-8")
        assert "runtime_mode_beep_blocks_non_beep_operation" in log_text
        assert "op=vibrate" in log_text
        assert "op=shock" in log_text
        assert fake.calls == []
    finally:
        temp_dir.cleanup()


def test_file_ingest_malformed_line_is_logged_without_crashing() -> None:
    temp_dir, log_path = _temp_log_path()
    try:
        configure_logging(log_path, force=True)
        source = Path(temp_dir.name) / "events.jsonl"
        source.write_text('{"bad"\n{"event_type":"player_healed"}\n', encoding="utf-8")

        generator = stream_jsonl(source, poll_interval_s=0.01)
        event = next(generator)
        generator.close()

        assert event["event_type"] == "player_healed"
        log_text = log_path.read_text(encoding="utf-8")
        assert "skipping invalid JSONL line" in log_text
        assert "line=1" in log_text
    finally:
        temp_dir.cleanup()
