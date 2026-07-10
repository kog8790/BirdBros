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
    def __init__(self, config: Optional[dict] = None, logger=None):
        self.config = config or {}
        self.logger = logger
        self.reward_config = self.config.get("reward_action", {})
        self.no_reward_config = self.config.get("no_reward_action", {})

    def _log_action(self, message: str, **data):
        if self.logger:
            try:
                self.logger.log_event("action", message, **data)
                return
            except Exception as e:
                print(f"[ACTION] Logger failed: {e}")

        if data:
            kv = " | ".join(f"{key}={value}" for key, value in data.items())
            print(f"[ACTION] {message} | {kv}")
        else:
            print(f"[ACTION] {message}")

    def reward(self, label: str = "Success"):
        print(f"[REWARD] Triggered for label: {label}")
        self._log_action("Reward action requested", label=label)
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
        self._log_action(
            "System interaction handler entered",
            mode="mouse_click",
            mechanism="pyautogui",
            pyautogui_available=pyautogui is not None,
            label=label
        )

        if pyautogui is None:
            message = "System interaction unavailable; pyautogui is not installed."
            print(f"[ACTION] {message}")
            self._log_action(
                message,
                mode="mouse_click",
                mechanism="pyautogui",
                label=label
            )
            return

        click_sequence = action_config.get("click_sequence")

        if isinstance(click_sequence, list):
            self._log_action(
                "System interaction sequence selected",
                mode="mouse_click",
                mechanism="pyautogui",
                step_count=len(click_sequence),
                label=label
            )
            self._mouse_click_sequence_action(click_sequence)
            return

        self._log_action(
            "Legacy system interaction selected",
            mode="mouse_click",
            mechanism="pyautogui",
            label=label
        )
        self._legacy_mouse_click_action(action_config)

    def _mouse_click_sequence_action(self, click_sequence: list):
        if not click_sequence:
            message = "System interaction skipped; mouse_click sequence is empty."
            print(f"[ACTION] {message}")
            self._log_action(
                message,
                mode="mouse_click",
                mechanism="pyautogui"
            )
            return

        self._log_action(
            "System interaction sequence started",
            mode="mouse_click",
            mechanism="pyautogui",
            step_count=len(click_sequence)
        )

        for index, step in enumerate(click_sequence, start=1):
            if not isinstance(step, dict):
                print(f"[ACTION] Skipping invalid system interaction step #{index}.")
                self._log_action(
                    "System interaction step skipped",
                    mode="mouse_click",
                    mechanism="pyautogui",
                    index=index,
                    reason="invalid_step"
                )
                continue

            x = step.get("x")
            y = step.get("y")

            if x is None or y is None:
                print(f"[ACTION] Skipping system interaction step #{index}; missing x/y.")
                self._log_action(
                    "System interaction step skipped",
                    mode="mouse_click",
                    mechanism="pyautogui",
                    index=index,
                    reason="missing_xy",
                    x=x,
                    y=y
                )
                continue

            hold_duration = max(0.0, float(step.get("hold_duration", 0.0)))
            delay_after = max(0.0, float(step.get("delay_after", 0.0)))
            move_duration = max(0.0, float(step.get("move_duration", 0.0)))

            self._log_action(
                "System interaction step attempted",
                mode="mouse_click",
                mechanism="pyautogui",
                index=index,
                x=x,
                y=y,
                hold_duration=hold_duration,
                delay_after=delay_after,
                move_duration=move_duration
            )

            try:
                pyautogui.moveTo(x, y, duration=move_duration)
                pyautogui.mouseDown(x, y)

                if hold_duration > 0:
                    pyautogui.sleep(hold_duration)

                pyautogui.mouseUp(x, y)

                if delay_after > 0:
                    pyautogui.sleep(delay_after)

                self._log_action(
                    "System interaction step completed",
                    mode="mouse_click",
                    mechanism="pyautogui",
                    index=index,
                    x=x,
                    y=y
                )

            except Exception as e:
                self._log_action(
                    "System interaction step failed",
                    mode="mouse_click",
                    mechanism="pyautogui",
                    index=index,
                    x=x,
                    y=y,
                    error=repr(e)
                )
                raise

        self._log_action(
            "System interaction sequence completed",
            mode="mouse_click",
            mechanism="pyautogui",
            step_count=len(click_sequence)
        )

    def _legacy_mouse_click_action(self, action_config: dict):
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

