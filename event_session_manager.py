""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages multiple concurrent event_session objects.

CORE FLOW:
- Receives object motion detections from motion_object_tracker
- Spawns a new session on every stable-to-motion transition in object ROI
- Updates existing sessions while motion continues
- Injects pre-event ring buffer frames into new sessions
- Completes sessions after detections disappear long enough
- Rejects weak/noisy sessions before they reach OpenAI
- Queues viable completed sessions for contact sheet analysis
"""

import math
from event_session import event_session


# ================================
# EVENT SESSION MANAGER
# ================================

class event_session_manager:
    def __init__(
        self,
        distance_threshold=75,
        max_missing_frames=3,
        max_active_sessions=8,
        min_event_frames=3,
        min_event_duration_seconds=0.10,
        min_event_path_distance=8.0
    ):
        self.distance_threshold = distance_threshold
        self.max_missing_frames = max_missing_frames
        self.max_active_sessions = max_active_sessions

        self.min_event_frames = min_event_frames
        self.min_event_duration_seconds = min_event_duration_seconds
        self.min_event_path_distance = min_event_path_distance

        self.active_sessions = []
        self.completed_sessions = []
        self.rejected_sessions = []

        self.previous_motion_detected = False


    # ================================
    # MAIN UPDATE ENTRYPOINT
    # ================================

    def update(self, detections, combined_frame, object_frame, pre_buffer=None):
        motion_detected = len(detections) > 0
        motion_started = motion_detected and not self.previous_motion_detected

        matched_sessions = set()

        if motion_started:
            self._spawn_session_from_motion_start(
                detections=detections,
                combined_frame=combined_frame,
                object_frame=object_frame,
                pre_buffer=pre_buffer or [],
                matched_sessions=matched_sessions
            )

        if motion_detected:
            self._update_sessions_from_detections(
                detections=detections,
                combined_frame=combined_frame,
                object_frame=object_frame,
                matched_sessions=matched_sessions
            )

        self._age_unmatched_sessions(
            matched_sessions=matched_sessions,
            combined_frame=combined_frame,
            object_frame=object_frame
        )

        self.previous_motion_detected = motion_detected


    # ================================
    # SESSION CREATION / UPDATES
    # ================================

    def _spawn_session_from_motion_start(
        self,
        detections,
        combined_frame,
        object_frame,
        pre_buffer,
        matched_sessions
    ):
        if len(self.active_sessions) >= self.max_active_sessions:
            return

        primary_detection = self._select_primary_detection(detections)

        if primary_detection is None:
            return

        new_session = self._create_session()
        new_session.missing_frames = 0

        new_session.update(
            combined_frame=combined_frame,
            object_frame=object_frame,
            motion_detected=True,
            centroid=primary_detection.get("centroid"),
            bbox=primary_detection.get("bbox"),
            area=primary_detection.get("area"),
            pre_event_records=pre_buffer
        )

        self.active_sessions.append(new_session)
        matched_sessions.add(new_session)

    def _update_sessions_from_detections(
        self,
        detections,
        combined_frame,
        object_frame,
        matched_sessions
    ):
        for detection in detections:
            centroid = detection.get("centroid")
            bbox = detection.get("bbox")
            area = detection.get("area")

            if centroid is None:
                continue

            matched_session = self._find_closest_session(centroid, matched_sessions)

            if not matched_session:
                continue

            matched_session.missing_frames = 0
            matched_session.update(
                combined_frame=combined_frame,
                object_frame=object_frame,
                motion_detected=True,
                centroid=centroid,
                bbox=bbox,
                area=area
            )

            matched_sessions.add(matched_session)

    def _create_session(self):
        return event_session(
            min_frames=self.min_event_frames,
            min_duration_seconds=self.min_event_duration_seconds,
            min_path_distance=self.min_event_path_distance
        )

    def _select_primary_detection(self, detections):
        valid_detections = [
            detection for detection in detections
            if detection.get("centroid") is not None
        ]

        if not valid_detections:
            return None

        return max(
            valid_detections,
            key=lambda detection: detection.get("area", 0)
        )


    # ================================
    # SESSION MATCHING
    # ================================

    def _find_closest_session(self, centroid, already_matched):
        closest_session = None
        closest_distance = None

        for session in self.active_sessions:
            if session in already_matched:
                continue

            last_centroid = self._get_last_centroid(session)

            if last_centroid is None:
                continue

            distance = self._distance(centroid, last_centroid)

            if distance > self.distance_threshold:
                continue

            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest_session = session

        return closest_session

    def _get_last_centroid(self, session):
        records = session.get_records()

        for record in reversed(records):
            centroid = record.get("centroid")
            if centroid is not None:
                return centroid

        return None


    # ================================
    # SESSION AGING / COMPLETION
    # ================================

    def _age_unmatched_sessions(self, matched_sessions, combined_frame, object_frame):
        for session in list(self.active_sessions):
            if session in matched_sessions:
                continue

            session.missing_frames = getattr(session, "missing_frames", 0) + 1

            if session.missing_frames >= self.max_missing_frames:
                session.update(
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    motion_detected=False,
                    centroid=None,
                    bbox=None,
                    area=None
                )

                self._complete_session(session)

    def _complete_session(self, session):
        if session in self.active_sessions:
            self.active_sessions.remove(session)

        if session.is_viable():
            self.completed_sessions.append(session)
        else:
            self.rejected_sessions.append(session)

            print(
                "[SESSION_REJECTED]",
                f"reason={session.get_rejection_reason()}",
                f"frames={len(session.get_records())}",
                f"duration={session.get_duration_seconds():.3f}",
                f"path_length={session.get_event_path_length():.1f}"
            )

    # ================================
    # READY EVENT QUEUE
    # ================================

    def get_next_ready_event(self):
        if not self.completed_sessions:
            return None

        return self.completed_sessions.pop(0)
        
    def get_next_rejected_event(self):
        if not self.rejected_sessions:
            return None

        return self.rejected_sessions.pop(0)

    # ================================
    # RESET / HELPERS
    # ================================

    def reset(self):
        self.active_sessions = []
        self.completed_sessions = []
        self.rejected_sessions = []
        self.previous_motion_detected = False

    def _distance(self, a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def get_active_count(self):
        return len(self.active_sessions)

    def get_completed_count(self):
        return len(self.completed_sessions)

    def get_rejected_count(self):
        return len(self.rejected_sessions)


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
motion_object_tracker.detect(object_crop)
    ↓
event_session_manager.update(...)
    ↓
stable-to-motion edge creates a new session
    ↓
active sessions update from matching detections
    ↓
unmatched sessions age out and complete
    ↓
weak sessions are rejected before API
    ↓
main.py pulls viable completed session
    ↓
contact_sheet_builder builds grid
    ↓
OpenAI analyzes event sequence

DESIGN INTENT:
This class decides whether object ROI motion forms a distinct viable event.
It does not call OpenAI, trigger rewards, or write storyboards.
"""
