""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages one object-triggered event and prepares frames for contact sheet analysis.

CORE FLOW:
- Receive pre-event frames from the always-on ring buffer
- Buffer event frames while object motion is active
- Track centroid movement as supporting evidence
- Select a small ordered frame set for contact sheet generation
- Stay independent from OpenAI, reward logic, and UI concerns
"""

import time
import cv2
import math


# ================================
# EVENT SESSION
# ================================

class event_session:
    def __init__(
        self,
        max_buffer_size=40,
        min_frames=2,
        pre_event_target_count=4,
        event_target_count=8
    ):
        self.max_buffer_size = max_buffer_size
        self.min_frames = min_frames
        self.pre_event_target_count = pre_event_target_count
        self.event_target_count = event_target_count

        self.active = False
        self.completed = False
        self.ready_sent = False

        self.start_time = None
        self.end_time = None

        self.pre_event_records = []
        self.records = []

        self.best_record = None


    # ================================
    # SESSION LIFECYCLE
    # ================================

    def start(self, pre_event_records=None):
        self.active = True
        self.completed = False
        self.ready_sent = False

        self.start_time = time.time()
        self.end_time = None

        self.best_record = None

        self.records = []
        self.pre_event_records = self._copy_limited_records(
            pre_event_records or [],
            limit=self.max_buffer_size
        )


    def end(self):
        self.active = False
        self.completed = True
        self.end_time = time.time()
        self.best_record = self._select_best_event_record()


    def reset(self):
        self.active = False
        self.completed = False
        self.ready_sent = False

        self.start_time = None
        self.end_time = None

        self.pre_event_records = []
        self.records = []

        self.best_record = None


    # ================================
    # UPDATE LOOP ENTRYPOINT
    # ================================

    def update(
        self,
        combined_frame,
        object_frame,
        motion_detected,
        centroid=None,
        bbox=None,
        area=None,
        pre_event_records=None
    ):
        if not self.active and motion_detected:
            self.start(pre_event_records=pre_event_records)

        if self.active and motion_detected:
            self._add_record(
                combined_frame=combined_frame,
                object_frame=object_frame,
                centroid=centroid,
                bbox=bbox,
                area=area
            )
            return "active"

        if self.active and not motion_detected:
            self._add_record(
                combined_frame=combined_frame,
                object_frame=object_frame,
                centroid=centroid,
                bbox=bbox,
                area=area
            )
            self.end()

            if self.has_records() and not self.ready_sent:
                self.ready_sent = True
                return "ready"

            return "complete"

        return None


    # ================================
    # RECORD STORAGE
    # ================================

    def _add_record(self, combined_frame, object_frame, centroid=None, bbox=None, area=None):
        record = {
            "timestamp": time.time(),
            "combined_frame": combined_frame.copy(),
            "object_frame": object_frame.copy(),
            "centroid": centroid,
            "bbox": bbox,
            "area": area,
            "sharpness": self._calculate_sharpness(combined_frame),
            "source": "event"
        }

        self.records.append(record)

        if len(self.records) > self.max_buffer_size:
            self.records = self.records[-self.max_buffer_size:]


    def _copy_limited_records(self, records, limit):
        copied = []
        limited_records = records[-limit:]

        previous_object_frame = None

        for record in limited_records:
            object_frame = record["object_frame"].copy()

            centroid = record.get("centroid")

            if centroid is None and previous_object_frame is not None:
                centroid = self._estimate_motion_centroid(
                    previous_object_frame,
                    object_frame
                )

            copied.append({
                "timestamp": record.get("timestamp", time.time()),
                "combined_frame": record["combined_frame"].copy(),
                "object_frame": object_frame,
                "subject_frame": record.get("subject_frame").copy() if record.get("subject_frame") is not None else None,
                "centroid": centroid,
                "bbox": record.get("bbox"),
                "area": record.get("area"),
                "sharpness": record.get("sharpness", self._calculate_sharpness(record["combined_frame"])),
                "source": record.get("source", "pre")
            })

            previous_object_frame = object_frame.copy()

        return copied


    # ================================
    # CONTACT SHEET FRAME SELECTION
    # ================================

    def get_contact_sheet_frames(self, max_frames=12):
        pre_frames = self._select_pre_event_frames(self.pre_event_records)
        event_frames = self._select_event_frames(self.records)

        selected = pre_frames + event_frames
        selected = sorted(selected, key=lambda record: record["timestamp"])

        if len(selected) > max_frames:
            selected = self._evenly_sample(selected, max_frames)

        return selected


    def _select_pre_event_frames(self, records):
        if not records:
            return []

        stable_records = sorted(
            records,
            key=lambda record: record.get("sharpness", 0),
            reverse=True
        )

        selected = stable_records[:self.pre_event_target_count]
        return sorted(selected, key=lambda record: record["timestamp"])


    def _select_event_frames(self, records):
        if not records:
            return []

        records_with_centroid = [
            record for record in records
            if record.get("centroid") is not None
        ]

        if len(records_with_centroid) >= 2:
            return self._select_centroid_diverse_frames(
                records_with_centroid,
                target_count=self.event_target_count
            )

        sharp_records = sorted(
            records,
            key=lambda record: record.get("sharpness", 0),
            reverse=True
        )

        selected = sharp_records[:self.event_target_count]
        return sorted(selected, key=lambda record: record["timestamp"])


    def _select_centroid_diverse_frames(self, records, target_count):
        if len(records) <= target_count:
            return sorted(records, key=lambda record: record["timestamp"])

        path_length = self._calculate_path_length(records)

        if path_length <= 0:
            return self._evenly_sample(records, target_count)

        selected = []
        target_distances = [
            (path_length * i) / max(1, target_count - 1)
            for i in range(target_count)
        ]

        cumulative = 0.0
        previous = records[0]

        selected.append(previous)

        target_index = 1

        for record in records[1:]:
            cumulative += self._centroid_distance(previous, record)

            while target_index < len(target_distances) and cumulative >= target_distances[target_index]:
                selected.append(record)
                target_index += 1

            previous = record

        if records[-1] not in selected:
            selected.append(records[-1])

        selected = self._dedupe_records(selected)

        if len(selected) > target_count:
            selected = self._rank_by_sharpness_then_sample(selected, target_count)

        return sorted(selected, key=lambda record: record["timestamp"])


    def _evenly_sample(self, records, target_count):
        if len(records) <= target_count:
            return records

        if target_count <= 1:
            return [records[0]]

        step = (len(records) - 1) / (target_count - 1)
        indexes = [round(i * step) for i in range(target_count)]

        return [records[index] for index in indexes]


    def _rank_by_sharpness_then_sample(self, records, target_count):
        sharp_records = sorted(
            records,
            key=lambda record: record.get("sharpness", 0),
            reverse=True
        )

        selected = sharp_records[:target_count]
        return sorted(selected, key=lambda record: record["timestamp"])


    # ================================
    # BEST RECORD SUPPORT
    # ================================

    def _select_best_event_record(self):
        if not self.records:
            return None

        records_with_centroid = [
            record for record in self.records
            if record.get("centroid") is not None
        ]

        if len(records_with_centroid) >= 2:
            midpoint = self._trajectory_midpoint(records_with_centroid)

            def score(record):
                cx, cy = record["centroid"]
                distance = math.hypot(cx - midpoint[0], cy - midpoint[1])
                sharpness_bonus = record.get("sharpness", 0) * 0.001
                return distance - sharpness_bonus

            return min(records_with_centroid, key=score)

        return max(self.records, key=lambda record: record.get("sharpness", 0))


    def get_best_record(self):
        return self.best_record


    # ================================
    # METRICS / HELPERS
    # ================================
    
    def _estimate_motion_centroid(self, previous_frame, current_frame):
        if previous_frame is None or current_frame is None:
            return None

        if previous_frame.size == 0 or current_frame.size == 0:
            return None

        previous_gray = cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY)
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)

        previous_gray = cv2.GaussianBlur(previous_gray, (21, 21), 0)
        current_gray = cv2.GaussianBlur(current_gray, (21, 21), 0)

        frame_delta = cv2.absdiff(previous_gray, current_gray)

        thresh = cv2.threshold(
            frame_delta,
            25,
            255,
            cv2.THRESH_BINARY
        )[1]

        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area <= 0:
            return None

        moments = cv2.moments(largest)

        if moments["m00"] == 0:
            x, y, w, h = cv2.boundingRect(largest)
            return (x + w // 2, y + h // 2)

        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])

        return (cx, cy)

    def _calculate_sharpness(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()


    def _centroid_distance(self, record_a, record_b):
        ax, ay = record_a["centroid"]
        bx, by = record_b["centroid"]
        return math.hypot(bx - ax, by - ay)


    def _calculate_path_length(self, records):
        total = 0.0

        for i in range(1, len(records)):
            total += self._centroid_distance(records[i - 1], records[i])

        return total


    def _trajectory_midpoint(self, records):
        first = records[0]["centroid"]
        last = records[-1]["centroid"]

        return (
            (first[0] + last[0]) / 2,
            (first[1] + last[1]) / 2
        )


    def _dedupe_records(self, records):
        seen = set()
        deduped = []

        for record in records:
            key = record["timestamp"]

            if key not in seen:
                seen.add(key)
                deduped.append(record)

        return deduped


    # ================================
    # PUBLIC STATE ACCESS
    # ================================

    def has_records(self):
        return len(self.records) >= self.min_frames
        
    def get_full_centroid_path(self):
        path = []

        for record in self.pre_event_records + self.records:
            centroid = record.get("centroid")

            if centroid is not None:
                path.append(centroid)

        return path

    def get_records(self):
        return self.records


    def get_pre_event_records(self):
        return self.pre_event_records


    def is_active(self):
        return self.active


    def is_complete(self):
        return self.completed


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
main.py ring buffer
    ↓
event_session.start(pre_event_records)
    ↓
event_session buffers object-motion frames
    ↓
event_session selects pre-event + event frames
    ↓
contact_sheet_builder creates ordered grid
    ↓
OpenAI analyzes sequence

DESIGN INTENT:
Centroid helps select useful event frames, but AI makes the final interpretation.
"""
