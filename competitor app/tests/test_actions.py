import os

import pytest

from competitor_app.actions import ActionContext, ActionError, ActionRunner
from competitor_app.config import RewardAction


def test_webhook_headers_are_not_mutated_when_token_is_added(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers, timeout))
        return Response()

    monkeypatch.setenv("TOKEN_ENV", "secret")
    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    action = RewardAction(kind="webhook", url="https://example.test/hook", headers={"X-Test": "1"}, bearer_token_env="TOKEN_ENV")

    result = ActionRunner().run(action, ActionContext(True, "label", "reason"))

    assert result == "webhook:200"
    assert calls[0][2]["Authorization"] == "Bearer secret"
    assert "Authorization" not in action.headers


def test_shell_command_requires_runtime_env_gate():
    action = RewardAction(kind="shell_command", command=("echo", "ok"))
    os.environ.pop("COMPETITOR_ALLOW_SHELL_ACTIONS", None)

    with pytest.raises(ActionError):
        ActionRunner().run(action, ActionContext(True, "label", "reason"))
