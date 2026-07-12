""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages one behavior episode and prepares behavior-relevant frames for
contact sheet analysis.

CORE FLOW:
- Receive pre-event frames from the always-on ring buffer
- Buffer event frames while an episode is active
- Store visual-change metrics from frame_change_analyzer.py
- Treat centroid movement as a useful signal, not the gatekeeper
- Select an ordered, role-balanced, low-duplicate frame set for contact sheets
- Reject only obvious junk before expensive API analysis

DESIGN PIVOT:
The ROI is the trigger/focus anchor.
The whole capture region provides behavioral context.
Centroid/object motion boosts useful frames, but does not dominate selection.
"""

import time
import cv2
import math
import numpy as np


# ================================
# EVENT SESSION
# ================================

class event_session:
    def __init__(
        self,
        max_buffer_size=60,
        min_frames=3,
        min_duration_seconds=0.0,
        min_path_distance=8.0,
        pre_event_target_count=3,
        event_target_count=9,
        minimum_importance_score=0.01,
        duplicate_similarity_threshold=0.972
    ):
        self.max_buffer_size = max_buffer_size
        self.min_frames = min_frames
        self.min_duration_seconds = min_duration_seconds

        # Kept for logging/debug compatibility.
        # No longer used as a hard rejection rule.
        self.min_path_distance = min_path_distance

        self.pre_event_target_count = pre_event_target_count
        self.event_target_count = event_target_count
        self.minimum_importance_score = minimum_importance_score
        self.duplicate_similarity_threshold = duplicate_similarity_threshold

        self.active = False
        self.completed = False
        self.ready_sent = False

        self.start_time = None
        self.end_time = None

        self.pre_event_records = []
        self.records = []

        self.best_record = None
        self.rejection_reason = None

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
        self.rejection_reason = None

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
        self.rejection_reason = None

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
        pre_event_records=None,
        change_metrics=None,
        keep_alive=False
    ):
        if not self.active and motion_detected:
            self.start(pre_event_records=pre_event_records)

        if self.active and (motion_detected or keep_alive):
            self._add_record(
                combined_frame=combined_frame,
                object_frame=object_frame,
                centroid=centroid,
                bbox=bbox,
                area=area,
                motion_detected=motion_detected,
                change_metrics=change_metrics
            )
            return "active"

        if self.active and not motion_detected and not keep_alive:
            self._add_record(
                combined_frame=combined_frame,
                object_frame=object_frame,
                centroid=centroid,
                bbox=bbox,
                area=area,
                motion_detected=False,
                change_metrics=change_metrics
            )

            self.end()

            if self.is_viable() and not self.ready_sent:
                self.ready_sent = True
                return "ready"

            return "rejected"

        return None

    # ================================
    # RECORD STORAGE
    # ================================

    def _add_record(
        self,
        combined_frame,
        object_frame,
        centroid=None,
        bbox=None,
        area=None,
        motion_detected=True,
        change_metrics=None
    ):
        if combined_frame is None:
            return

        change_metrics = change_metrics or {}

        now = time.time()
        event_record_index = len(self.records)

        previous_timestamp = None
        if self.records:
            previous_timestamp = self.records[-1].get("timestamp")

        record = {
            "timestamp": now,
            "event_record_index": event_record_index,
            "event_elapsed_s": (now - self.start_time) if self.start_time else 0.0,
            "seconds_since_previous_record": (now - previous_timestamp) if previous_timestamp else 0.0,

            "combined_frame": combined_frame.copy(),
            "object_frame": object_frame.copy() if object_frame is not None else None,
            "centroid": centroid,
            "bbox": bbox,
            "area": area,
            "motion_detected": motion_detected,
            "sharpness": self._calculate_sharpness(combined_frame),
            "source": "event",

            "scene_delta": float(change_metrics.get("scene_delta", 0.0)),
            "roi_delta": float(change_metrics.get("roi_delta", 0.0)),
            "regional_delta": float(change_metrics.get("regional_delta", 0.0)),
            "scene_changed_ratio": float(change_metrics.get("scene_changed_ratio", 0.0)),
            "roi_changed_ratio": float(change_metrics.get("roi_changed_ratio", 0.0)),
            "is_scene_novel": bool(change_metrics.get("is_scene_novel", False)),
            "is_roi_novel": bool(change_metrics.get("is_roi_novel", False)),
            "is_regionally_novel": bool(change_metrics.get("is_regionally_novel", False)),
            "is_meaningfully_different": bool(change_metrics.get("is_meaningfully_different", False)),
            "change_importance_score": float(change_metrics.get("importance_score", 0.0)),
            "dominant_region": change_metrics.get("dominant_region"),
        }

        record["centroid_motion_score"] = self._calculate_centroid_motion_score(record)
        record["importance_score"] = self._calculate_record_importance(record)
        record["selection_role"] = self._infer_selection_role(record)

        self.records.append(record)

        if len(self.records) > self.max_buffer_size:
            self.records = self.records[-self.max_buffer_size:]

    def _copy_limited_records(self, records, limit):
        copied = []
        limited_records = records[-limit:]

        previous_object_frame = None

        for record in limited_records:
            combined_frame = record.get("combined_frame")
            object_frame = record.get("object_frame")

            if combined_frame is None:
                continue

            combined_copy = combined_frame.copy()
            object_copy = object_frame.copy() if object_frame is not None else None

            centroid = record.get("centroid")

            if centroid is None and previous_object_frame is not None and object_copy is not None:
                centroid = self._estimate_motion_centroid(
                    previous_object_frame,
                    object_copy
                )

            copied_record = {
                "timestamp": record.get("timestamp", time.time()),
                "event_record_index": record.get("event_record_index"),
                "event_elapsed_s": record.get("event_elapsed_s"),
                "seconds_since_previous_record": record.get("seconds_since_previous_record"),

                "combined_frame": combined_copy,
                "object_frame": object_copy,
                "subject_frame": record.get("subject_frame").copy() if record.get("subject_frame") is not None else None,
                "centroid": centroid,
                "bbox": record.get("bbox"),
                "area": record.get("area"),
                "motion_detected": record.get("motion_detected", False),
                "sharpness": record.get("sharpness", self._calculate_sharpness(combined_copy)),
                "source": record.get("source", "pre"),

                "scene_delta": float(record.get("scene_delta", 0.0)),
                "roi_delta": float(record.get("roi_delta", 0.0)),
                "regional_delta": float(record.get("regional_delta", 0.0)),
                "scene_changed_ratio": float(record.get("scene_changed_ratio", 0.0)),
                "roi_changed_ratio": float(record.get("roi_changed_ratio", 0.0)),
                "is_scene_novel": bool(record.get("is_scene_novel", False)),
                "is_roi_novel": bool(record.get("is_roi_novel", False)),
                "is_regionally_novel": bool(record.get("is_regionally_novel", False)),
                "is_meaningfully_different": bool(record.get("is_meaningfully_different", False)),
                "change_importance_score": float(record.get("change_importance_score", record.get("importance_score", 0.0))),
                "centroid_motion_score": float(record.get("centroid_motion_score", 0.0)),
                "dominant_region": record.get("dominant_region"),
            }

            copied_record["importance_score"] = self._calculate_record_importance(copied_record)
            copied_record["selection_role"] = self._infer_selection_role(copied_record)

            copied.append(copied_record)

            if object_copy is not None:
                previous_object_frame = object_copy.copy()

        return copied

    # ================================
    # CONTACT SHEET FRAME SELECTION
    # ================================

    def get_contact_sheet_frames(self, max_frames=12):
        if max_frames <= 0:
            return []

        pre_quota = min(self.pre_event_target_count, max(1, max_frames // 4))
        event_quota = max(1, max_frames - pre_quota)

        selected = []
        selected.extend(self._select_pre_event_frames(self.pre_event_records, pre_quota))
        selected.extend(self._select_event_frames(self.records, event_quota))

        selected = self._dedupe_records(selected)
        selected = sorted(selected, key=lambda record: record["timestamp"])

        if len(selected) > max_frames:
            selected = self._select_diverse_story_frames(selected, max_frames)

        return sorted(selected, key=lambda record: record["timestamp"])

    def _select_pre_event_frames(self, records, target_count=None):
        if not records:
            return []

        target_count = target_count or self.pre_event_target_count

        if len(records) <= target_count:
            return sorted(records, key=lambda record: record["timestamp"])

        selected = []

        self._append_if_useful(selected, records[0], role="pre_start", allow_duplicate=False)
        self._append_if_useful(selected, records[-1], role="pre_last", allow_duplicate=False)

        if len(selected) < target_count:
            candidates = sorted(
                records,
                key=lambda record: (
                    record.get("importance_score", 0.0),
                    record.get("scene_delta", 0.0),
                    record.get("sharpness", 0.0)
                ),
                reverse=True
            )

            for record in candidates:
                if len(selected) >= target_count:
                    break

                self._append_if_useful(selected, record, role="pre_context", allow_duplicate=False)

        if len(selected) < target_count:
            for record in self._evenly_sample(records, target_count):
                if len(selected) >= target_count:
                    break
                self._append_if_useful(selected, record, role="pre_context", allow_duplicate=True)

        return sorted(self._dedupe_records(selected), key=lambda record: record["timestamp"])

    def _select_event_frames(self, records, target_count=None):
        if not records:
            return []

        target_count = target_count or self.event_target_count

        if len(records) <= target_count:
            self._assign_basic_roles(records)
            return sorted(records, key=lambda record: record["timestamp"])

        selected = []

        role_candidates = [
            ("event_start", records[0]),
            ("first_motion", self._first_matching_record(records, "motion_detected")),
            ("first_roi_change", self._first_matching_record(records, "is_roi_novel")),
            ("best_scene_change", self._best_record_by(records, "scene_delta")),
            ("best_regional_change", self._best_record_by(records, "regional_delta")),
            ("best_roi_change", self._best_record_by(records, "roi_delta")),
            ("best_centroid_motion", self._best_record_by(records, "centroid_motion_score")),
            ("best_overall", self._best_record_by(records, "importance_score")),
            ("event_end", records[-1]),
        ]

        for role, record in role_candidates:
            if len(selected) >= target_count:
                break

            self._append_if_useful(
                selected,
                record,
                role=role,
                allow_duplicate=False,
                role_critical=True
            )

        if len(selected) < target_count:
            for record in self._rank_behavior_useful_candidates(records):
                if len(selected) >= target_count:
                    break

                self._append_if_useful(
                    selected,
                    record,
                    role=self._infer_selection_role(record),
                    allow_duplicate=False
                )

        if len(selected) < target_count:
            for record in self._evenly_sample(records, target_count):
                if len(selected) >= target_count:
                    break

                self._append_if_useful(
                    selected,
                    record,
                    role=self._infer_selection_role(record),
                    allow_duplicate=True
                )

        selected = self._dedupe_records(selected)

        if len(selected) > target_count:
            selected = self._select_diverse_story_frames(selected, target_count)

        return sorted(selected, key=lambda record: record["timestamp"])

    def _rank_behavior_useful_candidates(self, records):
        return sorted(
            records,
            key=lambda record: (
                self._balanced_story_score(record),
                record.get("importance_score", 0.0),
                record.get("sharpness", 0.0)
            ),
            reverse=True
        )

    def _balanced_story_score(self, record):
        # Whole-scene and regional context stay central.
        # ROI/object/centroid signals boost priority without owning the sheet.
        scene_delta = float(record.get("scene_delta", 0.0))
        regional_delta = float(record.get("regional_delta", 0.0))
        roi_delta = float(record.get("roi_delta", 0.0))
        centroid_score = float(record.get("centroid_motion_score", 0.0))
        change_score = float(record.get("change_importance_score", 0.0))

        motion_bonus = 0.07 if record.get("motion_detected") else 0.0
        centroid_bonus = 0.06 if record.get("centroid") is not None else 0.0

        return self._clamp01(
            scene_delta * 0.26
            + regional_delta * 0.22
            + roi_delta * 0.24
            + change_score * 0.14
            + centroid_score * 0.08
            + motion_bonus
            + centroid_bonus
        )

    def _append_if_useful(
        self,
        selected,
        record,
        role=None,
        allow_duplicate=False,
        role_critical=False
    ):
        if record is None:
            return False

        if record in selected:
            return False

        if not allow_duplicate and self._is_visually_duplicate(record, selected):
            if role_critical:
                replaced = self._replace_weaker_duplicate(selected, record, role)
                if replaced:
                    return True
            return False

        if role:
            record["selection_role"] = role

        selected.append(record)
        return True

    def _replace_weaker_duplicate(self, selected, record, role=None):
        duplicate_index = None

        for index, selected_record in enumerate(selected):
            if self._frame_similarity(
                record.get("combined_frame"),
                selected_record.get("combined_frame")
            ) >= self.duplicate_similarity_threshold:
                duplicate_index = index
                break

        if duplicate_index is None:
            return False

        existing = selected[duplicate_index]

        if self._balanced_story_score(record) <= self._balanced_story_score(existing):
            return False

        if role:
            record["selection_role"] = role

        selected[duplicate_index] = record
        return True

    def _select_diverse_story_frames(self, records, target_count):
        if len(records) <= target_count:
            return records

        selected = []

        self._append_if_useful(selected, records[0], role=records[0].get("selection_role", "start"), allow_duplicate=True)
        self._append_if_useful(selected, records[-1], role=records[-1].get("selection_role", "end"), allow_duplicate=True)

        for record in self._rank_behavior_useful_candidates(records[1:-1]):
            if len(selected) >= target_count:
                break

            self._append_if_useful(
                selected,
                record,
                role=record.get("selection_role", self._infer_selection_role(record)),
                allow_duplicate=False
            )

        if len(selected) < target_count:
            for record in self._evenly_sample(records, target_count):
                if len(selected) >= target_count:
                    break

                self._append_if_useful(
                    selected,
                    record,
                    role=record.get("selection_role", self._infer_selection_role(record)),
                    allow_duplicate=True
                )

        return sorted(self._dedupe_records(selected[:target_count]), key=lambda record: record["timestamp"])

    def _evenly_sample(self, records, target_count):
        if len(records) <= target_count:
            return records

        if target_count <= 1:
            return [records[0]]

        step = (len(records) - 1) / (target_count - 1)
        indexes = [round(i * step) for i in range(target_count)]

        return [records[index] for index in indexes]

    # ================================
    # RECORD ROLES
    # ================================

    def _assign_basic_roles(self, records):
        for record in records:
            record["selection_role"] = self._infer_selection_role(record)

        if records:
            records[0]["selection_role"] = "event_start"
            records[-1]["selection_role"] = "event_end"

    def _infer_selection_role(self, record):
        if record.get("source") == "pre":
            return "pre_context"

        centroid_score = float(record.get("centroid_motion_score", 0.0))
        roi_delta = float(record.get("roi_delta", 0.0))
        scene_delta = float(record.get("scene_delta", 0.0))
        regional_delta = float(record.get("regional_delta", 0.0))

        if centroid_score >= max(roi_delta, scene_delta, regional_delta, 0.01):
            return "centroid_motion"

        if roi_delta >= max(scene_delta, regional_delta, 0.01):
            return "roi_change"

        if regional_delta >= max(scene_delta, 0.01):
            return "regional_change"

        if scene_delta >= 0.01:
            return "scene_change"

        if record.get("motion_detected"):
            return "motion"

        return "context"

    # ================================
    # BEST RECORD SUPPORT
    # ================================

    def _select_best_event_record(self):
        if not self.records:
            return None

        return max(
            self.records,
            key=lambda record: (
                self._balanced_story_score(record),
                record.get("importance_score", 0.0),
                record.get("sharpness", 0.0)
            )
        )

    def get_best_record(self):
        return self.best_record

    def get_first_stable_record(self):
        for record in self.records:
            if record.get("motion_detected") is False:
                return record

        if self.records:
            return self.records[-1]

        return None

    # ================================
    # VIABILITY FILTERS
    # ================================

    def is_viable(self):
        if len(self.records) < self.min_frames:
            self.rejection_reason = "too_few_frames"
            return False

        if self.min_duration_seconds > 0 and self.get_duration_seconds() < self.min_duration_seconds:
            self.rejection_reason = "too_short_duration"
            return False

        if not self._has_meaningful_event_signal():
            self.rejection_reason = "too_little_visual_change"
            return False

        self.rejection_reason = None
        return True

    def _has_meaningful_event_signal(self):
        if not self.records:
            return False

        if any(record.get("motion_detected") for record in self.records):
            return True

        if any(record.get("is_meaningfully_different") for record in self.records):
            return True

        best_importance = max(
            record.get("importance_score", 0.0)
            for record in self.records
        )

        return best_importance >= self.minimum_importance_score

    def get_rejection_reason(self):
        return self.rejection_reason

    def get_duration_seconds(self):
        if self.start_time is None:
            return 0.0

        end_time = self.end_time or time.time()
        return max(0.0, end_time - self.start_time)

    def get_event_path_length(self):
        records_with_centroid = [
            record for record in self.records
            if record.get("centroid") is not None
        ]

        if len(records_with_centroid) < 2:
            return 0.0

        return self._calculate_path_length(records_with_centroid)

    # ================================
    # IMPORTANCE SCORING
    # ================================

    def _calculate_record_importance(self, record):
        scene_delta = float(record.get("scene_delta", 0.0))
        roi_delta = float(record.get("roi_delta", 0.0))
        regional_delta = float(record.get("regional_delta", 0.0))
        change_importance = float(record.get("change_importance_score", 0.0))
        centroid_score = float(record.get("centroid_motion_score", 0.0))
        sharpness_score = self._normalize_sharpness(record.get("sharpness", 0.0))

        source_bonus = 0.04 if record.get("source") == "pre" else 0.0
        motion_bonus = 0.07 if record.get("motion_detected") else 0.0
        centroid_bonus = 0.06 if record.get("centroid") is not None else 0.0

        score = (
            scene_delta * 0.22
            + regional_delta * 0.20
            + roi_delta * 0.22
            + change_importance * 0.16
            + centroid_score * 0.08
            + sharpness_score * 0.05
            + source_bonus
            + motion_bonus
            + centroid_bonus
        )

        return self._clamp01(score)

    def _calculate_centroid_motion_score(self, record):
        centroid = record.get("centroid")

        if centroid is None or not self.records:
            return 0.0

        previous_centroid = None

        for previous_record in reversed(self.records):
            if previous_record.get("centroid") is not None:
                previous_centroid = previous_record["centroid"]
                break

        if previous_centroid is None:
            return 0.0

        distance = math.hypot(
            centroid[0] - previous_centroid[0],
            centroid[1] - previous_centroid[1]
        )

        return self._clamp01(distance / 75.0)

    def _normalize_sharpness(self, sharpness):
        return self._clamp01(float(sharpness) / 1000.0)

    # ================================
    # VISUAL SIMILARITY
    # ================================

    def _is_visually_duplicate(self, record, selected_records):
        if not selected_records:
            return False

        for selected_record in selected_records:
            similarity = self._frame_similarity(
                record.get("combined_frame"),
                selected_record.get("combined_frame")
            )

            if similarity >= self.duplicate_similarity_threshold:
                return True

        return False

    def _frame_similarity(self, frame_a, frame_b):
        if frame_a is None or frame_b is None:
            return 0.0

        gray_a = self._small_gray(frame_a)
        gray_b = self._small_gray(frame_b)

        if gray_a is None or gray_b is None:
            return 0.0

        if gray_a.shape != gray_b.shape:
            gray_b = cv2.resize(
                gray_b,
                (gray_a.shape[1], gray_a.shape[0]),
                interpolation=cv2.INTER_AREA
            )

        diff = cv2.absdiff(gray_a, gray_b)
        mean_diff = float(np.mean(diff)) / 255.0

        return self._clamp01(1.0 - mean_diff)

    def _small_gray(self, frame, width=96):
        if frame is None or not hasattr(frame, "size") or frame.size == 0:
            return None

        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        height, original_width = gray.shape[:2]

        if original_width <= 0 or height <= 0:
            return None

        scale = width / float(original_width)
        new_height = max(1, int(height * scale))

        return cv2.resize(
            gray,
            (width, new_height),
            interpolation=cv2.INTER_AREA
        )

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
        if frame is None:
            return 0.0

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
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

    def _first_matching_record(self, records, field_name):
        for record in records:
            if record.get(field_name):
                return record

        return None

    def _best_record_by(self, records, field_name):
        if not records:
            return None

        return max(
            records,
            key=lambda record: record.get(field_name, 0.0) or 0.0
        )

    def _dedupe_records(self, records):
        seen = set()
        deduped = []

        for record in records:
            key = record.get("timestamp")

            if key not in seen:
                seen.add(key)
                deduped.append(record)

        return deduped

    def _clamp01(self, value):
        return max(0.0, min(1.0, float(value)))

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
frame_change_analyzer creates visual-change metrics
    ↓
event_session.start(pre_event_records)
    ↓
event_session buffers ROI-triggered + scene-novel frames
    ↓
event_session filters only obvious junk
    ↓
event_session selects role-balanced behavior frames
    ↓
contact_sheet_builder creates ordered grid
    ↓
OpenAI analyzes sequence

DESIGN INTENT:
Centroid and object/ROI motion boost frame priority.
Whole-scene and regional visual change preserve behavior context.
The contact sheet should tell a balanced behavior story, not just a motion path.
"""

