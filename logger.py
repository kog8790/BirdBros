""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Handles structured runtime logging for Bird Bros.

RESPONSIBILITIES:
- Log general events
- Log motion state changes
- Log API calls/results
- Log reward/no-reward outcomes
- Log storyboard events

DESIGN INTENT:
Provide a lightweight memory layer without coupling logging to runtime logic. """

import os
import json
import shutil
from datetime import datetime, timedelta


class Logger:
    def __init__(
        self,
        log_dir="logs",
        text_log_file="birdbros.log",
        jsonl_log_file="birdbros.jsonl"
    ):
        self.log_dir = log_dir
        self.text_log_file = text_log_file
        self.jsonl_log_file = jsonl_log_file

        os.makedirs(self.log_dir, exist_ok=True)

        self.text_log_path = os.path.join(self.log_dir, self.text_log_file)
        self.jsonl_log_path = os.path.join(self.log_dir, self.jsonl_log_file)

    def _timestamp(self):
        return datetime.now().isoformat(timespec="seconds")
        
    def purge_old_files(self, log_retention_days=90, storyboard_retention_days=14):
        now = datetime.now()

        # ----------------------------
        # Purge old log files
        # ----------------------------

        for filename in os.listdir(self.log_dir):

            path = os.path.join(self.log_dir, filename)

            if not os.path.isfile(path):
                continue

            modified = datetime.fromtimestamp(os.path.getmtime(path))

            if now - modified > timedelta(days=log_retention_days):
                os.remove(path)

        # ----------------------------
        # Purge old storyboard folders
        # ----------------------------

        storyboard_root = os.path.join(self.log_dir, "storyboards")

        if not os.path.exists(storyboard_root):
            return

        for folder_name in os.listdir(storyboard_root):

            folder_path = os.path.join(
                storyboard_root,
                folder_name
            )

            if not os.path.isdir(folder_path):
                continue

            modified = datetime.fromtimestamp(
                os.path.getmtime(folder_path)
            )

            if now - modified > timedelta(days=storyboard_retention_days):
                shutil.rmtree(folder_path)

    """ ### SEGMENT: LOGGING METHODS ###
    Standardized logging helpers for runtime, API, reward, motion, and storyboard events. """
    def log_event(self, event_type: str, message: str, **data):
        timestamp = self._timestamp()

        text_line = f"[{timestamp}] {event_type.upper()} | {message}"
        if data:
            kv = " | ".join(f"{k}={v}" for k, v in data.items())
            text_line += f" | {kv}"

        with open(self.text_log_path, "a", encoding="utf-8") as f:
            f.write(text_line + "\n")

        json_record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "message": message,
            "data": data
        }

        with open(self.jsonl_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(json_record, ensure_ascii=False) + "\n")

        print(text_line)

    def log_info(self, message: str, **data):
        self.log_event("info", message, **data)

    def log_warning(self, message: str, **data):
        self.log_event("warning", message, **data)

    def log_error(self, message: str, **data):
        self.log_event("error", message, **data)

    def log_reward(self, success: bool, label: str = "", **data):
        event_type = "reward" if success else "no_reward"
        message = "Reward triggered" if success else "No reward"
        self.log_event(event_type, message, label=label, **data)

    def log_motion(self, zone: str, detected: bool, **data):
        self.log_event(
            "motion",
            f"Motion {'detected' if detected else 'cleared'} in {zone}",
            zone=zone,
            detected=detected,
            **data
        )

    def log_api_call(self, stage: str, **data):
        self.log_event("api_call", f"OpenAI call: {stage}", stage=stage, **data)

    def log_api_result(self, stage: str, **data):
        self.log_event("api_result", f"OpenAI result: {stage}", stage=stage, **data)

    def log_storyboard_event(self, session_id: str, event_type: str, **data):
        self.log_event(
            "storyboard",
            f"Storyboard event recorded: {event_type}",
            session_id=session_id,
            event_type_detail=event_type,
            **data
        )

    def log_storyboard_finalized(self, session_id: str, rewarded: bool, label: str, **data):
        self.log_event(
            "storyboard_finalized",
            "Storyboard finalized",
            session_id=session_id,
            rewarded=rewarded,
            label=label,
            **data
        )


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
main.py / session_storyboard.py
    ↓
Logger
    ↓
text log + JSONL log + terminal output """
