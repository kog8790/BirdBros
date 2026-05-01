"""                 ### SEGMENT: FILE OVERVIEW ###

PURPOSE:
Handles screen capture of a defined region using mss and returns frames
in a format usable by OpenCV.

This is the ONLY module allowed to interface with the screen/camera feed.

RESPONSIBILITIES:
- Capture frames from macOS screen (iPhone mirroring window region)
- Return frames as numpy arrays (BGR format for OpenCV)
- Maintain consistent frame dimensions based on capture region

USED BY:
- main.py (frame acquisition loop)

INPUTS:
- region dict: {left, top, width, height}

OUTPUTS:
- frame (numpy array): shape (H, W, 3), BGR format          """


import numpy as np
import cv2
import mss


"""     ### SEGMENT: CLASS DEFINITION (cam_controller) ###

ROLE:
Encapsulates screen capture logic and abstracts away mss usage.

STATE:
- region: capture area (dict)
- sct: mss instance

BEHAVIOR:
- Maintains persistent mss session for performance
- Captures raw screen pixels from specified region
- Converts to numpy array usable by OpenCV pipeline

IMPORTANT:
- Coordinates must match the same space used by ROI logic in main.py
- No scaling or transformation should occur here
- Returns raw, unmodified pixel data            """
class cam_controller:
    def __init__(self, region, fps=30):
        """
        region example:
        {
            "top": 100,
            "left": 200,
            "width": 800,
            "height": 600
        }
        """
        self.region = region
        self.fps = fps
        self.sct = mss.mss()

    """ ### SEGMENT: FRAME CAPTURE ###
    get_frame():
    Captures screen region via mss and returns BGR numpy frame (H, W, 3)."""
    def get_frame(self):
        screenshot = self.sct.grab(self.region)
        frame = np.array(screenshot)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    def capture_frame(self):
        return self.get_frame()

    def go_dormant(self):
        pass



"""             ### SEGMENT: SYSTEM CONTEXT ###

FLOW:

control_panel.py
    ↓ (user defines capture_region)
main.py
    ↓ (passes region into cam_controller)
cam_controller.py
    ↓ (captures frame via mss)
main.py
    ↓ (applies ROI % → pixel conversion)
bound_box_define → cropping → motion detection → vision API

CONSTRAINTS:
- No other module should access mss or screen directly
- This module must remain simple and deterministic

DESIGN INTENT:
Keep capture logic isolated so:
- coordinate bugs are easier to trace
- performance remains stable
- future camera sources (USB cam, RTSP, etc.) can be swapped in         """
