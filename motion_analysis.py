"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Provides higher-level motion interpretation beyond simple detection, including
centroid tracking, stability assessment, and directional analysis.

RESPONSIBILITIES:
- Analyze motion patterns over time
- Track centroid movement
- Determine stability of motion
- Support selection of best frame from motion sequences

USED BY:
- subject_session (stabilization + best frame logic)
- main.py (indirectly through session flow)

INPUTS:
- Frame sequences or motion-triggered frames

OUTPUTS:
- Stability signals
- Motion characteristics (centroid, movement behavior)

DESIGN INTENT:
Bridge raw motion detection and session logic with reusable motion analysis tools.
"""


import cv2
import numpy as np

""" ### SEGMENT: MOTION ANALYSIS LOGIC ###
Contains core functions for interpreting motion behavior, including:
- centroid tracking
- movement consistency
- stability detection

These functions operate on sequences or buffered frames rather than single-frame input.
"""

class motion_analysis:
    def __init__(
        self,
        diff_threshold=25,
        stable_threshold=5000,
        blur_kernel=(21, 21)
    ):
        self.diff_threshold = diff_threshold
        self.stable_threshold = stable_threshold
        self.blur_kernel = blur_kernel

    def to_gray_blur(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self.blur_kernel, 0)
        return gray

    def sharpness_score(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()

    def frame_difference_score(self, frame_a, frame_b):
        gray_a = self.to_gray_blur(frame_a)
        gray_b = self.to_gray_blur(frame_b)

        frame_delta = cv2.absdiff(gray_a, gray_b)
        thresh = cv2.threshold(
            frame_delta,
            self.diff_threshold,
            255,
            cv2.THRESH_BINARY
        )[1]

        motion_score = int(np.sum(thresh > 0))
        return motion_score

    def is_stable(self, frames):
        """
        Returns True if the most recent frame transition is calm enough
        to be considered stabilized.
        """
        if len(frames) < 2:
            return False

        recent_score = self.frame_difference_score(frames[-2], frames[-1])
        return recent_score < self.stable_threshold

    def select_best_frame(self, frames):
        """
        Picks the sharpest frame from the buffered session.
        """
        if not frames:
            return None

        best_frame = None
        best_score = -1

        for frame in frames:
            score = self.sharpness_score(frame)
            if score > best_score:
                best_score = score
                best_frame = frame

        return best_frame

    def get_motion_scores(self, frames):
        """
        Returns a list of motion scores between consecutive frames.
        """
        scores = []

        if len(frames) < 2:
            return scores

        for i in range(1, len(frames)):
            score = self.frame_difference_score(frames[i - 1], frames[i])
            scores.append(score)

        return scores

    def get_centroid(self, frame):
        """
        Returns the centroid of the largest detected motion region in a frame.
        This is optional helper functionality for future path tracking.
        """
        gray = self.to_gray_blur(frame)

        _, thresh = cv2.threshold(
            gray,
            self.diff_threshold,
            255,
            cv2.THRESH_BINARY
        )

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        moments = cv2.moments(largest)

        if moments["m00"] == 0:
            return None

        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
        return (cx, cy)





"""                 ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

cam_controller → frames
    ↓
motion_detector → motion signal
    ↓
motion_triggered_buffer (optional)
    ↓
motion_analysis
    ↓
subject_session (stability + best frame selection)
    ↓
vision_api

DESIGN INTENT:
Provide reusable motion intelligence without embedding logic directly in session or main.
"""
