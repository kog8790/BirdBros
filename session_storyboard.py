""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Creates a narrative record of each analyzed Bird Bros event.

RESPONSIBILITIES:
- Start and finalize storyboard sessions
- Save key images for review
- Store API results and final outcome
- Write story.json and story.txt
- Preserve task labels used for each event

DESIGN INTENT:
Make every decision reviewable: what the system saw, what prompt labels it used,
and why reward/no-reward was selected. """

import os
import json
import cv2
from datetime import datetime


class session_storyboard:
    def __init__(self, logger=None, root_dir="logs/storyboards"):
        self.logger = logger
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)
        self.reset()

    # ================================
    # SESSION LIFECYCLE
    # ================================

    def reset(self):
        self.active = False
        self.session_id = None
        self.session_dir = None
        self.started_at = None
        self.ended_at = None
        self.events = []
        self.event_counter = 0
        self.final_outcome = None
        self.task_labels = {}

    def start_session(self, opening_frame=None, notes="", task_labels=None):
        self.reset()

        self.active = True
        self.started_at = self._timestamp()
        self.session_id = f"session_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        self.session_dir = os.path.join(self.root_dir, self.session_id)
        self.task_labels = task_labels or {}

        os.makedirs(self.session_dir, exist_ok=True)

        self.add_event(
            event_type="session_started",
            frame=opening_frame,
            notes=notes,
            data={"task_labels": self.task_labels}
        )

    def finalize(
        self,
        rewarded: bool,
        label: str = "",
        frame=None,
        subject_frame=None,
        object_frame=None,
        notes: str = ""
    ):
        if not self.active:
            return

        self.final_outcome = {
            "rewarded": rewarded,
            "label": label
        }

        self.add_event(
            event_type="final_outcome",
            frame=frame,
            subject_frame=subject_frame,
            object_frame=object_frame,
            notes=notes,
            data=self.final_outcome
        )

        self.ended_at = self._timestamp()
        self._write_story_files()

        if self.logger:
            self.logger.log_storyboard_finalized(
                session_id=self.session_id,
                rewarded=rewarded,
                label=label,
                story_dir=self.session_dir,
                story_json_path=os.path.join(self.session_dir, "story.json"),
                story_txt_path=os.path.join(self.session_dir, "story.txt")
            )

        self.active = False

    def abort(self, notes="Storyboard aborted"):
        if not self.active:
            return

        self.finalize(
            rewarded=False,
            label="aborted",
            notes=notes
        )

    # ================================
    # EVENT RECORDING
    # ================================

    def add_event(
        self,
        event_type: str,
        frame=None,
        subject_frame=None,
        object_frame=None,
        notes: str = "",
        data=None
    ):
        if not self.active:
            self.start_session(opening_frame=frame, notes="Session auto-started")

        safe_data = self._safe_data(data or {})

        image_filename = self._save_frame(frame, event_type, "frame")
        subject_image_filename = self._save_frame(subject_frame, event_type, "subject")
        object_image_filename = self._save_frame(object_frame, event_type, "object")

        record = {
            "timestamp": self._timestamp(),
            "type": event_type,
            "notes": notes,
            "image": image_filename,
            "subject_image": subject_image_filename,
            "object_image": object_image_filename,
            "data": safe_data
        }

        self.events.append(record)

        if self.logger:
            self.logger.log_storyboard_event(
                session_id=self.session_id,
                event_type=event_type,
                image=image_filename,
                subject_image=subject_image_filename,
                object_image=object_image_filename,
                notes=notes
            )

        return record

    # ================================
    # FRAME SAVING
    # ================================

    def _save_frame(self, frame, event_type: str, suffix: str = "frame"):
        if frame is None or self.session_dir is None:
            return None

        self.event_counter += 1
        filename = f"{self.event_counter:02d}_{self._slug(event_type)}_{suffix}.jpg"
        path = os.path.join(self.session_dir, filename)
        cv2.imwrite(path, frame)
        return filename

    # ================================
    # STORY FILE WRITING
    # ================================

    def _write_story_files(self):
        if not self.session_dir:
            return

        story_json = {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "task_labels": self.task_labels,
            "final_outcome": self.final_outcome,
            "events": self.events
        }

        json_path = os.path.join(self.session_dir, "story.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(story_json, f, indent=2)

        txt_path = os.path.join(self.session_dir, "story.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Bird Bros Storyboard | {self.session_id}\n\n")
            f.write(f"Started: {self.started_at}\n")
            f.write(f"Ended: {self.ended_at}\n\n")

            if self.task_labels:
                f.write("Task Labels:\n")
                for key, value in self.task_labels.items():
                    f.write(f"- {key}: {value}\n")
                f.write("\n")

            for event in self.events:
                image_note = ""
                if event.get("image"):
                    image_note = f" (image: {event['image']})"
                f.write(f"- [{event['timestamp']}] {event['type']}: {event['notes']}{image_note}\n")

            f.write("\nNarrative Summary:\n")
            if self.final_outcome and self.final_outcome.get("rewarded"):
                f.write("The session ended with reward.\n")
            else:
                f.write("The session ended without reward.\n")

            if self.final_outcome:
                f.write(
                    f"\nFinal Outcome: rewarded={self.final_outcome.get('rewarded')} "
                    f"| label={self.final_outcome.get('label')}\n"
                )

    # ================================
    # HELPERS
    # ================================

    def _timestamp(self):
        return datetime.now().isoformat(timespec="seconds")

    def _slug(self, text):
        if text is None:
            return "none"

        text = str(text).strip().lower()
        safe = []

        for char in text:
            if char.isalnum():
                safe.append(char)
            elif char in [" ", "-", "_", "/", ":", ".", ","]:
                safe.append("_")

        slug = "".join(safe)
        while "__" in slug:
            slug = slug.replace("__", "_")

        return slug.strip("_") or "event"

    def _safe_data(self, data):
        try:
            json.dumps(data)
            return data
        except TypeError:
            return {key: str(value) for key, value in data.items()}


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
main.py
    ↓
session_storyboard.start_session()
    ↓
add_event() saves contact sheets / frames
    ↓
finalize() writes story.json + story.txt

DESIGN INTENT:
Storyboards preserve enough context to debug AI decisions after the run. """
