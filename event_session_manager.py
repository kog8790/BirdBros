""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Manages behavior episodes created by trigger-ROI motion.

CORE FLOW:
- ROI motion starts a candidate episode
- Visual novelty can keep the episode alive after ROI motion disappears
- Repeated ROI hits can join the same episode if the scene never settled
- Completed viable sessions are queued for API/contact-sheet analysis
- Rejected sessions are queued for storyboard/debug review

DESIGN PIVOT:
The ROI is the trigger/focus anchor, not the whole event.
Centroid is useful for association, not the event definition.
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
        min_event_duration_seconds=0.0,
        min_event_path_distance=8.0,
        max_session_frames=90,
        allow_reacquire_existing_session=True
    ):
        self.distance_threshold = distance_threshold

        # Now means "quiet frames after novelty/motion disappears",
        # not simply "missing centroid frames."
        self.max_missing_frames = max_missing_frames

        self.max_active_sessions = max_active_sessions

        self.min_event_frames = min_event_frames
        self.min_event_duration_seconds = min_event_duration_seconds

        # Kept for compatibility/debug. event_session no longer uses this
        # as a hard rejection rule.
        self.min_event_path_distance = min_event_path_distance

        # Safety cap. Not a behavior timing assumption; prevents endless sessions.
        self.max_session_frames = max_session_frames

        self.allow_reacquire_existing_session = allow_reacquire_existing_session

        self.active_sessions = []
        self.completed_sessions = []
        self.rejected_sessions = []

        self.previous_motion_detected = False

    # ================================
    # MAIN UPDATE ENTRYPOINT
    # ================================

    def update(
        self,
        detections,
        combined_frame,
        object_frame,
        pre_buffer=None,
        change_metrics=None
    ):
        detections = detections or []
        pre_buffer = pre_buffer or []
        change_metrics = change_metrics or {}

        motion_detected = len(detections) > 0
        motion_started = motion_detected and not self.previous_motion_detected
        scene_is_novel = self._is_scene_novel(change_metrics)

        matched_sessions = set()

        if motion_started and not self.active_sessions:
            self._spawn_session_from_motion_start(
                detections=detections,
                combined_frame=combined_frame,
                object_frame=object_frame,
                pre_buffer=pre_buffer,
                change_metrics=change_metrics,
                matched_sessions=matched_sessions
            )

        if motion_detected:
            self._update_sessions_from_detections(
                detections=detections,
                combined_frame=combined_frame,
                object_frame=object_frame,
                change_metrics=change_metrics,
                matched_sessions=matched_sessions
            )

        self._update_unmatched_sessions(
            matched_sessions=matched_sessions,
            combined_frame=combined_frame,
            object_frame=object_frame,
            change_metrics=change_metrics,
            scene_is_novel=scene_is_novel
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
        change_metrics,
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
            pre_event_records=pre_buffer,
            change_metrics=change_metrics,
            keep_alive=True
        )

        self.active_sessions.append(new_session)
        matched_sessions.add(new_session)

    def _update_sessions_from_detections(
        self,
        detections,
        combined_frame,
        object_frame,
        change_metrics,
        matched_sessions
    ):
        if not self.active_sessions:
            return

        for detection in detections:
            centroid = detection.get("centroid")
            bbox = detection.get("bbox")
            area = detection.get("area")

            if centroid is None:
                continue

            matched_session = self._find_closest_session(
                centroid=centroid,
                already_matched=matched_sessions
            )

            if matched_session is None and self.allow_reacquire_existing_session:
                matched_session = self._find_reacquire_session(
                    already_matched=matched_sessions
                )

            if matched_session is None:
                continue

            matched_session.missing_frames = 0

            matched_session.update(
                combined_frame=combined_frame,
                object_frame=object_frame,
                motion_detected=True,
                centroid=centroid,
                bbox=bbox,
                area=area,
                change_metrics=change_metrics,
                keep_alive=True
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

    def _find_reacquire_session(self, already_matched):
        candidates = [
            session for session in self.active_sessions
            if session not in already_matched
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda session: self._session_recent_importance(session)
        )

    def _get_last_centroid(self, session):
        records = session.get_records()

        for record in reversed(records):
            centroid = record.get("centroid")
            if centroid is not None:
                return centroid

        return None

    def _session_recent_importance(self, session):
        records = session.get_records()

        if not records:
            return 0.0

        recent_records = records[-5:]

        return max(
            record.get("importance_score", 0.0)
            for record in recent_records
        )

    # ================================
    # SESSION AGING / COMPLETION
    # ================================

    def _update_unmatched_sessions(
        self,
        matched_sessions,
        combined_frame,
        object_frame,
        change_metrics,
        scene_is_novel
    ):
        for session in list(self.active_sessions):
            if session in matched_sessions:
                continue

            if self._session_hit_safety_cap(session):
                self._finish_session(
                    session=session,
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    change_metrics=change_metrics
                )
                continue

            if scene_is_novel:
                session.missing_frames = 0

                session.update(
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    motion_detected=False,
                    centroid=None,
                    bbox=None,
                    area=None,
                    change_metrics=change_metrics,
                    keep_alive=True
                )

                continue

            session.missing_frames = getattr(session, "missing_frames", 0) + 1

            if session.missing_frames >= self.max_missing_frames:
                self._finish_session(
                    session=session,
                    combined_frame=combined_frame,
                    object_frame=object_frame,
                    change_metrics=change_metrics
                )

    def _finish_session(
        self,
        session,
        combined_frame,
        object_frame,
        change_metrics
    ):
        session.update(
            combined_frame=combined_frame,
            object_frame=object_frame,
            motion_detected=False,
            centroid=None,
            bbox=None,
            area=None,
            change_metrics=change_metrics,
            keep_alive=False
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

    def _session_hit_safety_cap(self, session):
        return len(session.get_records()) >= self.max_session_frames

    # ================================
    # VISUAL NOVELTY SUPPORT
    # ================================

    def _is_scene_novel(self, change_metrics):
        if not change_metrics:
            return False

        if change_metrics.get("is_meaningfully_different"):
            return True

        if change_metrics.get("is_scene_novel"):
            return True

        if change_metrics.get("is_roi_novel"):
            return True

        if change_metrics.get("is_regionally_novel"):
            return True

        return False

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
frame_change_analyzer.analyze(...)
    ↓
event_session_manager.update(...)
    ↓
ROI motion starts candidate episode
    ↓
visual novelty keeps episode alive
    ↓
repeated ROI hits can reconnect to same episode
    ↓
event_session selects behavior-relevant frames
    ↓
contact_sheet_builder builds grid
    ↓
OpenAI judges configured behavior

DESIGN INTENT:
This class manages episode boundaries.
It should not decide reward, call OpenAI, or write storyboards.
"""
