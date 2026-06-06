"""                     ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Executes the final outcome of the system (reward or no-reward) based on validation results.

RESPONSIBILITIES:
- Trigger reward actions (e.g., mouse click, API call, keyboard input)
- Handle non-reward outcomes
- Support configurable action modes

USED BY:
- main.py (final step in decision pipeline)

INPUTS:
- Label / result context
- Config-defined action parameters

OUTPUTS:
- Side effects (UI interaction, hardware trigger, API call)

DESIGN INTENT:
Abstract reward behavior so different implementations (clicks, webhooks, etc.)
can be swapped without changing core logic.                                 """


import subprocess
import shlex
from typing import Optional

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import requests
except ImportError:
    requests = None

"""                     ### SEGMENT: REWARD EXECUTION ###
reward():
Executes configured reward action based on current mode (click, keypress, webhook, etc.).                                                          """

class resulting_action:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.reward_config = self.config.get("reward_action", {})
        self.no_reward_config = self.config.get("no_reward_action", {})

    def reward(self, label: str = "Success"):
        print(f"[REWARD] Triggered for label: {label}")
        self._dispatch(self.reward_config, label, is_reward=True)

    """         ### SEGMENT: NO-REWARD HANDLING ###
    no_reward():
    Handles non-reward outcomes (logging, optional feedback)."""
    def no_reward(self, label: str = "No reward"):
        print(f"[NO REWARD] Triggered for label: {label}")
        self._dispatch(self.no_reward_config, label, is_reward=False)

    def _dispatch(self, action_config: dict, label: str, is_reward: bool):
        mode = action_config.get("mode", "debug_popup").strip().lower()

        if mode in ("debug_popup", "overlay_status"):
            event_type = "reward" if is_reward else "no_reward"
            print(f"[ACTION] Overlay status mode: {event_type} | label={label}")
            return

        if mode == "mouse_click":
            self._mouse_click_action(action_config, label)
            return

        if mode == "keyboard_shortcut":
            self._keyboard_shortcut_action(action_config, label)
            return

        if mode == "webhook":
            self._webhook_action(action_config, label, is_reward)
            return

        if mode == "shell_command":
            self._shell_command_action(action_config, label, is_reward)
            return

        print(f"[ACTION] Unknown mode '{mode}'. No action performed.")

    def _mouse_click_action(self, action_config: dict, label: str):
        if pyautogui is None:
            print("[ACTION] pyautogui is not installed. Cannot perform mouse_click action.")
            return

        x = action_config.get("x")
        y = action_config.get("y")
        clicks = int(action_config.get("clicks", 1))
        interval = float(action_config.get("interval", 0.1))
        duration = float(action_config.get("move_duration", 0.0))

        if x is None or y is None:
            print("[ACTION] mouse_click mode requires 'x' and 'y'.")
            return

        pyautogui.moveTo(x, y, duration=duration)

        for _ in range(clicks):
            pyautogui.click(x, y)
            if interval > 0:
                pyautogui.sleep(interval)

    def _keyboard_shortcut_action(self, action_config: dict, label: str):
        if pyautogui is None:
            print("[ACTION] pyautogui is not installed. Cannot perform keyboard_shortcut action.")
            return

        keys = action_config.get("keys", [])
        interval = float(action_config.get("interval", 0.0))

        if not keys or not isinstance(keys, list):
            print("[ACTION] keyboard_shortcut mode requires a list of 'keys'.")
            return

        pyautogui.hotkey(*keys, interval=interval)

    def _webhook_action(self, action_config: dict, label: str, is_reward: bool):
        if requests is None:
            print("[ACTION] requests is not installed. Cannot perform webhook action.")
            return

        url = action_config.get("url")
        method = action_config.get("method", "POST").upper()
        timeout = float(action_config.get("timeout", 5))
        headers = action_config.get("headers", {})
        payload = action_config.get("payload", {})
        bearer_token = action_config.get("bearer_token", "").strip()
        
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        if not url:
            print("[ACTION] webhook mode requires 'url'.")
            return

        body = {
            "event": "reward" if is_reward else "no_reward",
            "label": label,
            **payload
        }

        try:
            if method == "POST":
                response = requests.post(url, json=body, headers=headers, timeout=timeout)
            elif method == "GET":
                response = requests.get(url, params=body, headers=headers, timeout=timeout)
            else:
                print(f"[ACTION] Unsupported webhook method '{method}'.")
                return

            print(f"[ACTION] Webhook response: {response.status_code}")
        except Exception as e:
            print(f"[ACTION] Webhook failed: {e}")

    def _shell_command_action(self, action_config: dict, label: str, is_reward: bool):
        command = action_config.get("command", "")

        if not command:
            print("[ACTION] shell_command mode requires 'command'.")
            return

        command = command.replace("{label}", label)
        command = command.replace("{event}", "reward" if is_reward else "no_reward")

        try:
            subprocess.run(shlex.split(command), check=False)
        except Exception as e:
            print(f"[ACTION] Shell command failed: {e}")
                
        
"""                ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

vision_api → object validation
    ↓
main.py decision
    ↓
resulting_action.reward() OR no_reward()
    ↓
external effect (treat dispense, feedback, etc.)

DESIGN INTENT:
Keep all side-effect logic isolated from detection and decision-making layers.
"""

