import json

import telegram_bot


def test_telegram_health_file_contains_only_safe_operational_state(tmp_path, monkeypatch):
    health_path = tmp_path / "telegram_health.json"
    monkeypatch.setattr(telegram_bot, "TELEGRAM_HEALTH_PATH", health_path)

    telegram_bot._write_telegram_health(
        "degraded",
        consecutiveFailures=2,
        lastSuccessAt="2026-09-05T18:00:00+08:00",
        errorType="TimeoutError",
    )

    payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert payload["status"] == "degraded"
    assert payload["consecutiveFailures"] == 2
    assert payload["errorType"] == "TimeoutError"
    assert "token" not in json.dumps(payload).lower()
