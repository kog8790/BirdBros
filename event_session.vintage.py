""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages one bounded motion event inside an ROI.

RESPONSIBILITIES:
- Start when meaningful motion begins
- Buffer frames while motion continues
- Track optional centroids for trajectory analysis
- End when motion clears
- Select the best frame for API analysis

USED BY:
- main.py

INPUTS:
- Combined crop frame
- Object crop frame
- Motion boolean
- Optional centroid

OUTPUTS:
- Event state
- Best frame for API analysis
- Buffered event data

DESIGN INTENT:
Represent one meaningful motion event without knowing anything about OpenAI,
reward logic, animals, or litter.
"""

import time
import cv2
from motion_triggered_buffer import motion_triggered_buffer


""" ### SEGMENT: EVENT STATE MANAGEMENT ###
event_session

STATE:
- active event flag
- completed event flag
- buffered frames
- optional centroid path
- best frame selected after event ends

BEHAVIOR:
- Starts on motion
- Buffers while motion continues
- Completes when motion clears
- Selects best frame from buffered event

IMPORTANT:
One event_session should produce at most one API analysis.
"""
class event_session:
    def __init__(self, max_buffer_size=30, min_frames=2):
        self.max_buffer_size = max_buffer_size
        self.min_frames = min_frames

        self.buffer = motion_triggered_buffer(maxlen=max_buffer_size)

        self.active = False
        self.completed = False
        self.ready_sent = False

        self.start_time = None
        self.end_time = None

        self.best_frame = None
        self.best_record = None

        self.records = []

    def start(self):
        self.active = True
        self.completed = False
        self.ready_sent = False

        self.start_time = time.time()
        self.end_time = None

        self.best_frame = None
        self.best_record = None

        self.records = []
        self.buffer.clear()

    def end(self):
        self.active = False
        self.completed = True
        self.end_time = time.time()

        self.best_record = self._select_best_record()
        if self.best_record:
            self.best_frame = self.best_record.get("combined_frame")

    def reset(self):
        self.active = False
        self.completed = False
        self.ready_sent = False

        self.start_time = None
        self.end_time = None

        self.best_frame = None
        self.best_record = None

        self.records = []
        self.buffer.clear()

    def update(self, combined_frame, object_frame, motion_detected, centroid=None):
        if not self.active and motion_detected:
            self.start()

        if self.active and motion_detected:
            self._add_record(
                combined_frame=combined_frame,
                object_frame=object_frame,
                centroid=centroid
            )
            return "active"

        if self.active and not motion_detected:
            self._add_record(
                combined_frame=combined_frame,
                object_frame=object_frame,
                centroid=centroid
            )
            self.end()

            if self.has_best_frame() and not self.ready_sent:
                self.ready_sent = True
                return "ready"

            return "complete"

        return None

    def _add_record(self, combined_frame, object_frame, centroid=None):
        record = {
            "timestamp": time.time(),
            "combined_frame": combined_frame.copy(),
            "object_frame": object_frame.copy(),
            "centroid": centroid,
            "sharpness": self._calculate_sharpness(combined_frame)
        }

        self.records.append(record)
        self.buffer.add(combined_frame.copy())

    def _calculate_sharpness(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def _select_best_record(self):
        if len(self.records) < self.min_frames:
            return None

        records_with_centroid = [
            record for record in self.records
            if record.get("centroid") is not None
        ]

        if len(records_with_centroid) >= 2:
            entry = records_with_centroid[0]["centroid"]
            exit_point = records_with_centroid[-1]["centroid"]

            mid_x = (entry[0] + exit_point[0]) / 2
            mid_y = (entry[1] + exit_point[1]) / 2

            def score(record):
                cx, cy = record["centroid"]
                distance = ((cx - mid_x) ** 2 + (cy - mid_y) ** 2) ** 0.5
                return distance - (record["sharpness"] * 0.001)

            return min(records_with_centroid, key=score)

        return max(self.records, key=lambda record: record["sharpness"])

    def has_best_frame(self):
        return self.best_frame is not None

    def get_best_frame(self):
        return self.best_frame

    def get_best_record(self):
        return self.best_record

    def get_records(self):
        return self.records

    def is_active(self):
        return self.active

    def is_complete(self):
        return self.completed


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

object motion detector
    ↓
event_session.update()
    ↓
buffer combined/object frames
    ↓
motion clears
    ↓
select best combined frame
    ↓
main.py sends best frame to OpenAI

DESIGN INTENT:
Let the motion event define the API frame instead of relying on instant capture
or fixed delays.
"""
