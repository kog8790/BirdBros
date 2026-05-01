""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages multiple concurrent event_session objects.

CORE FLOW:
- Receives object motion detections from motion_object_tracker
- Matches detections to active sessions using centroid distance
- Creates new sessions for unmatched detections
- Injects pre-event ring buffer frames into new sessions
- Completes sessions after detections disappear
- Queues completed sessions for contact sheet analysis
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
        max_active_sessions=5
    ):
        self.distance_threshold = distance_threshold
        self.max_missing_frames = max_missing_frames
        self.max_active_sessions = max_active_sessions

        self.active_sessions = []
        self.completed_sessions = []


    # ================================
    # MAIN UPDATE ENTRYPOINT
    # ================================

    def update(self, detections, combined_frame, object_frame, pre_buffer=None):
        matched_sessions = set()

        for detection in detections:
            centroid = detection.get("centroid")
            bbox = detection.get("bbox")
            area = detection.get("area")

            if centroid is None:
                continue

            matched_session = self._find_closest_session(centroid, matched_sessions)

            if matched_session:
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

            else:
                if len(self.active_sessions) >= self.max_active_sessions:
                    continue

                new_session = event_session()
                new_session.missing_frames = 0
                new_session.update(
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    motion_detected=True,
                    centroid=centroid,
                    bbox=bbox,
                    area=area,
                    pre_event_records=pre_buffer or []
                )

                self.active_sessions.append(new_session)
                matched_sessions.add(new_session)

        self._age_unmatched_sessions(
            matched_sessions=matched_sessions,
            combined_frame=combined_frame,
            object_frame=object_frame
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

        if session.has_records():
            self.completed_sessions.append(session)


    # ================================
    # READY EVENT QUEUE
    # ================================

    def get_next_ready_event(self):
        if not self.completed_sessions:
            return None

        return self.completed_sessions.pop(0)


    # ================================
    # RESET / HELPERS
    # ================================

    def reset(self):
        self.active_sessions = []
        self.completed_sessions = []


    def _distance(self, a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])


    def get_active_count(self):
        return len(self.active_sessions)


    def get_completed_count(self):
        return len(self.completed_sessions)


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
motion_object_tracker.detect(object_crop)
    ↓
event_session_manager.update(...)
    ↓
match detection to active session OR start new session
    ↓
unmatched sessions age out and complete
    ↓
main.py pulls completed session
    ↓
contact_sheet_builder builds grid
    ↓
OpenAI analyzes event sequence

DESIGN INTENT:
This class manages event lifecycle only. It does not analyze images,
call OpenAI, trigger rewards, or write storyboards.
"""
