""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Detects moving objects inside the object ROI and returns trackable motion detections.

RESPONSIBILITIES:
- Compare current object ROI frame against previous frame
- Find motion contours
- Convert contours into bounding boxes and centroids
- Return detection records that can be assigned to event sessions

USED BY:
- main.py
- event_session_manager.py

INPUTS:
- object_crop frame from main.py

OUTPUTS:
- list of detections:
  {
      "centroid": (x, y),
      "bbox": (x, y, w, h),
      "area": float
  }

DESIGN INTENT:
Provide object-level motion details instead of a simple True/False signal,
allowing multiple event_sessions to coexist and be tracked independently.
"""

import cv2


""" ### SEGMENT: MOTION OBJECT TRACKER ###
motion_object_tracker

STATE:
- previous_frame: grayscale baseline for frame differencing
- min_area: minimum contour area required to count as meaningful motion
- blur_size: smoothing kernel to reduce noise

BEHAVIOR:
- Detects changed regions inside object ROI
- Converts those changes into centroid/bounding-box detections
- Does not manage sessions or call OpenAI
"""
class motion_object_tracker:
    def __init__(self, min_area=3000, blur_size=21, threshold_value=25):
        self.min_area = min_area
        self.blur_size = blur_size
        self.threshold_value = threshold_value
        self.previous_frame = None

    """ ### SEGMENT: DETECTION ###
    detect():
    Returns a list of motion detections from the current object ROI frame.
    """
    def detect(self, frame):
        detections = []

        if frame is None or frame.size == 0:
            return detections

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        if self.previous_frame is None:
            self.previous_frame = gray
            return detections

        if self.previous_frame.shape != gray.shape:
            self.previous_frame = gray
            return detections

        frame_delta = cv2.absdiff(self.previous_frame, gray)
        thresh = cv2.threshold(
            frame_delta,
            self.threshold_value,
            255,
            cv2.THRESH_BINARY
        )[1]

        thresh = cv2.dilate(thresh, None, iterations=2)

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour)

            if area < self.min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            centroid = self._calculate_centroid(contour, x, y, w, h)

            detections.append({
                "centroid": centroid,
                "bbox": (x, y, w, h),
                "area": area
            })

        self.previous_frame = gray

        detections.sort(key=lambda detection: detection["area"], reverse=True)
        return detections

    """ ### SEGMENT: CENTROID CALCULATION ###
    _calculate_centroid():
    Uses image moments when possible, otherwise falls back to bbox center.
    """
    def _calculate_centroid(self, contour, x, y, w, h):
        moments = cv2.moments(contour)

        if moments["m00"] != 0:
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            return (cx, cy)

        return (x + w // 2, y + h // 2)

    """ ### SEGMENT: RESET ###
    reset():
    Clears previous frame baseline when ROI/capture geometry changes.
    """
    def reset(self):
        self.previous_frame = None


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

main.py
    ↓
object_crop
    ↓
motion_object_tracker.detect()
    ↓
list of centroid/bbox detections
    ↓
event_session_manager assigns detections to active event_sessions

DESIGN INTENT:
Separate motion object extraction from event-session lifecycle management.
This file identifies "what moved"; another layer decides whether that movement
belongs to an existing event or starts a new one.
"""
