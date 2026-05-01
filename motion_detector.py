"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Performs lightweight motion detection using frame differencing on a per-ROI basis.

RESPONSIBILITIES:
- Detect motion between consecutive frames
- Maintain previous frame state
- Return simple boolean indicating motion presence

USED BY:
- main.py (called separately for subject and object ROIs)

INPUTS:
- Cropped frame (ROI-specific)

OUTPUTS:
- Boolean (True = motion detected)

DESIGN INTENT:
Keep motion detection fast and minimal, acting only as a trigger signal
for higher-level session logic."""

import cv2

"""             ### SEGMENT: CLASS DEFINITION ###
motion_detector

STATE:
- previous_frame (grayscale)
- min_area threshold

BEHAVIOR:
- Stores last frame
- Compares with current frame using absdiff
- Determines motion based on contour area

IMPORTANT:
Instance must persist across frames.
Do NOT reinitialize inside main loop."""

class motion_detector:
    def __init__(self, min_area=3000):
        self.previous_frame = None
        self.min_area = min_area

    def reset(self):
        self.previous_frame = None

    """         ### SEGMENT: MOTION DETECTION ###
detect(): Compares current frame to previous and returns True if motion exceeds threshold."""
    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if self.previous_frame is None:
            self.previous_frame = gray
            return False

        if self.previous_frame.shape != gray.shape:
            self.previous_frame = gray
            return False

        frame_delta = cv2.absdiff(self.previous_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        self.previous_frame = gray

        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                return True

        return False





"""                 ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

main.py
    ↓ (crop ROI)
motion_detector.detect()
    ↓ (bool)
subject_session / object logic
    ↓
API / reward decision

KEY BEHAVIOR:
- Runs independently for subject and object
- Drives session start/stop conditions

DESIGN INTENT:
Act as a fast gatekeeper to avoid unnecessary API calls and processing."""
