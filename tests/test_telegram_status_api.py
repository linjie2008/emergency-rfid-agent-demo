from subprocess import CompletedProcess
from unittest.mock import patch

from server import app, telegram_status


def test_telegram_status_route_is_registered():
    assert "/api/integrations/telegram/status" in {route.path for route in app.routes}


def test_telegram_status_does_not_expose_token():
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "secret-token"}):
        with patch("server.subprocess.run", return_value=CompletedProcess([], 0, stdout="active\n", stderr="")):
            result = telegram_status()
    assert result == {
        "integration": "telegram",
        "configured": True,
        "online": True,
        "status": "online",
        "serviceState": "active",
    }
    assert "secret-token" not in str(result)
