""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages multiple concurrent event_session instances based on object motion detections.

RESPONSIBILITIES:
- Maintain active event sessions
- Assign detections to the correct session (centroid proximity)
- Spawn new sessions for unmatched detections
- Mark sessions as missing when detections disappear
- Finalize sessions when motion stabilizes
- Queue completed sessions for downstream API analysis

USED BY:
- main.py

DEPENDS ON:
- event_session.py

DESIGN INTENT:
Allow multiple object-motion events to coexist without blocking each other.
This file does NOT perform vision analysis or reward logic — it only manages sessions.
"""

import time
import math
from event_session import event_session


""" ### SEGMENT: EVENT SESSION MANAGER ###
event_session_manager

STATE:
- active_sessions: currently tracking motion paths
- completed_sessions: sessions ready for analysis
- analyzed_sessions: sessions already consumed
- distance_threshold: max centroid distance to match an existing session
- max_missing_frames: frames allowed without detection before completing a session

BEHAVIOR:
- Update sessions each frame using current detections
- Match detections to sessions via centroid distance
- Spawn new sessions when no match found
- Finalize sessions when motion disappears
"""
class event_session_manager:
    def __init__(self, distance_threshold=75, max_missing_frames=3):
        self.active_sessions = []
        self.completed_sessions = []
        self.analyzed_sessions = []

        self.distance_threshold = distance_threshold
        self.max_missing_frames = max_missing_frames

    """ ### SEGMENT: MAIN UPDATE ###
    update():
    Called every frame from main.py with current detections and frame data.
    """
    def update(self, detections, combined_frame, object_frame):
        current_time = time.time()

        # Track which sessions got updated this frame
        updated_sessions = set()

        # --- Assign detections to existing sessions ---
        for detection in detections:
            centroid = detection["centroid"]

            matched_session = self._find_closest_session(centroid)

            if matched_session:
                matched_session.update(
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    motion_detected=True,
                    centroid=centroid
                )
                updated_sessions.add(matched_session)
            else:
                # Create new session
                new_session = event_session()
                new_session.update(
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    motion_detected=True,
                    centroid=centroid
                )
                self.active_sessions.append(new_session)
                updated_sessions.add(new_session)

        # --- Handle sessions that were NOT updated (missing) ---
        for session in list(self.active_sessions):
            if session not in updated_sessions:
                session.update(
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    motion_detected=False,
                    centroid=None
                )

                # If session is complete, move it
                if session.is_complete():
                    self._finalize_session(session)

    """ ### SEGMENT: MATCHING ###
    _find_closest_session():
    Returns nearest active session within distance threshold.
    """
    def _find_closest_session(self, centroid):
        closest_session = None
        min_distance = float("inf")

        for session in self.active_sessions:
            if not session.is_active():
                continue

            last_record = session.get_records()[-1] if session.get_records() else None
            if not last_record or not last_record.get("centroid"):
                continue

            sx, sy = last_record["centroid"]
            cx, cy = centroid

            distance = math.hypot(cx - sx, cy - sy)

            if distance < self.distance_threshold and distance < min_distance:
                closest_session = session
                min_distance = distance

        return closest_session

    """ ### SEGMENT: FINALIZATION ###
    _finalize_session():
    Moves session from active to completed list.
    """
    def _finalize_session(self, session):
        if session in self.active_sessions:
            self.active_sessions.remove(session)

        self.completed_sessions.append(session)

    """ ### SEGMENT: READY EVENT RETRIEVAL ###
    get_next_ready_event():
    Returns next completed session ready for analysis.
    """
    def get_next_ready_event(self):
        if not self.completed_sessions:
            return None

        session = self.completed_sessions.pop(0)
        self.analyzed_sessions.append(session)
        return session

    """ ### SEGMENT: RESET ###
    reset():
    Clears all sessions (used on config changes).
    """
    def reset(self):
        self.active_sessions = []
        self.completed_sessions = []
        self.analyzed_sessions = []


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

motion_object_tracker.detect()
    ↓
detections (centroids)
    ↓
event_session_manager.update()
    ↓
assign detections to sessions OR create new sessions
    ↓
sessions finalize when motion ends
    ↓
get_next_ready_event()
    ↓
main.py → OpenAI → reward/no reward

DESIGN INTENT:
Support multiple simultaneous object events while keeping each session independent.
"""

