from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from typing import Any

from .config import RewardAction


class ActionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ActionContext:
    rewardable: bool
    label: str
    reason: str


class ActionRunner:
    def run(self, action: RewardAction, context: ActionContext) -> str:
        if action.kind == "status":
            return f"status:{'reward' if context.rewardable else 'no_reward'}"
        if action.kind == "webhook":
            return self._webhook(action, context)
        if action.kind == "mouse_click":
            return self._mouse_click(action)
        if action.kind == "keyboard_shortcut":
            return self._keyboard_shortcut(action)
        if action.kind == "shell_command":
            return self._shell_command(action, context)
        raise ActionError(f"Unsupported action kind: {action.kind}")

    def _webhook(self, action: RewardAction, context: ActionContext) -> str:
        if not action.url:
            raise ActionError("Webhook action requires a URL")
        import requests

        headers = dict(action.headers)
        if action.bearer_token_env:
            token = os.getenv(action.bearer_token_env, "").strip()
            if not token:
                raise ActionError(f"Missing webhook token environment variable: {action.bearer_token_env}")
            headers["Authorization"] = f"Bearer {token}"
        body: dict[str, Any] = {
            "event": "reward" if context.rewardable else "no_reward",
            "label": context.label,
            "reason": context.reason,
            **action.payload,
        }
        if action.method == "POST":
            response = requests.post(action.url, json=body, headers=headers, timeout=action.timeout)
        else:
            response = requests.get(action.url, params=body, headers=headers, timeout=action.timeout)
        response.raise_for_status()
        return f"webhook:{response.status_code}"

    def _mouse_click(self, action: RewardAction) -> str:
        if not action.click_sequence:
            raise ActionError("Mouse click action requires at least one click step")
        import pyautogui

        for step in action.click_sequence:
            pyautogui.moveTo(step["x"], step["y"], duration=step["move_duration"])
            pyautogui.mouseDown(step["x"], step["y"])
            if step["hold_duration"] > 0:
                pyautogui.sleep(step["hold_duration"])
            pyautogui.mouseUp(step["x"], step["y"])
            if step["delay_after"] > 0:
                pyautogui.sleep(step["delay_after"])
        return f"mouse_click:{len(action.click_sequence)}"

    def _keyboard_shortcut(self, action: RewardAction) -> str:
        if not action.keys:
            raise ActionError("Keyboard shortcut action requires keys")
        import pyautogui

        pyautogui.hotkey(*action.keys)
        return f"keyboard_shortcut:{'+'.join(action.keys)}"

    def _shell_command(self, action: RewardAction, context: ActionContext) -> str:
        if os.getenv("COMPETITOR_ALLOW_SHELL_ACTIONS") != "1":
            raise ActionError("Shell actions require COMPETITOR_ALLOW_SHELL_ACTIONS=1")
        if not action.command:
            raise ActionError("Shell command action requires an argv command")
        env = os.environ.copy()
        env["COMPETITOR_EVENT"] = "reward" if context.rewardable else "no_reward"
        env["COMPETITOR_LABEL"] = context.label
        env["COMPETITOR_REASON"] = context.reason
        subprocess.run(list(action.command), check=True, env=env)
        return "shell_command:ok"
