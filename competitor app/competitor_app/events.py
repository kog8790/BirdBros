from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import cv2
import numpy as np

from .config import AppConfig, Roi


@dataclass(frozen=True)
class FrameRecord:
    frame: np.ndarray
    object_crop: np.ndarray
    motion_detected: bool
    motion_area: float


@dataclass(frozen=True)
class CompletedEvent:
    records: tuple[FrameRecord, ...]


class MotionEventDetector:
    def __init__(self, config: AppConfig):
        self.config = config
        self.previous_gray: np.ndarray | None = None
        self.pre_event: deque[FrameRecord] = deque(maxlen=config.motion.pre_event_frames)
        self.active: list[FrameRecord] = []
        self.still_count = 0

    def update(self, frame: np.ndarray) -> CompletedEvent | None:
        object_crop = crop_roi(frame, self.config.object_roi)
        motion_detected, motion_area = self._detect_motion(object_crop)
        record = FrameRecord(
            frame=context_frame(frame, self.config),
            object_crop=object_crop.copy(),
            motion_detected=motion_detected,
            motion_area=motion_area,
        )

        if motion_detected:
            if not self.active:
                self.active.extend(self.pre_event)
            self.active.append(record)
            self.still_count = 0
            self._trim_active()
            return None

        if self.active:
            self.active.append(record)
            self.still_count += 1
            self._trim_active()
            if self.still_count >= self.config.motion.still_frames_to_end:
                event = CompletedEvent(records=tuple(self.active))
                self.active = []
                self.still_count = 0
                self.pre_event.append(record)
                return event

        self.pre_event.append(record)
        return None

    def _detect_motion(self, object_crop: np.ndarray) -> tuple[bool, float]:
        gray = cv2.cvtColor(object_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if self.previous_gray is None:
            self.previous_gray = gray
            return False, 0.0
        delta = cv2.absdiff(self.previous_gray, gray)
        self.previous_gray = gray
        threshold = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = float(sum(cv2.contourArea(contour) for contour in contours))
        return area >= self.config.motion.min_area, area

    def _trim_active(self) -> None:
        if len(self.active) > self.config.motion.max_event_frames:
            self.active = self.active[-self.config.motion.max_event_frames:]


def crop_roi(frame: np.ndarray, roi: Roi) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, w, h = roi.to_pixels(width, height)
    return frame[y:y + h, x:x + w]


def context_frame(frame: np.ndarray, config: AppConfig) -> np.ndarray:
    if config.behavior.mode == "simple":
        return frame.copy()
    subject = config.subject_roi.to_pixels(frame.shape[1], frame.shape[0])
    obj = config.object_roi.to_pixels(frame.shape[1], frame.shape[0])
    x1 = min(subject[0], obj[0])
    y1 = min(subject[1], obj[1])
    x2 = max(subject[0] + subject[2], obj[0] + obj[2])
    y2 = max(subject[1] + subject[3], obj[1] + obj[3])
    return frame[y1:y2, x1:x2].copy()
