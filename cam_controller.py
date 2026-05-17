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


import threading
import time
import numpy as np
import cv2
import mss
from pathlib import Path

class cam_controller:
    def __init__(
        self,
        capture_region,
        fps=30,
        input_mode="screen_capture",
        video_path="",
        loop_video=True
    ):
        """
        region example:
        {
            "top": 100,
            "left": 200,
            "width": 800,
            "height": 600
        }
        """
        self.capture_region = capture_region
        self.fps = fps

        self.input_mode = input_mode
        self.video_path = video_path
        self.loop_video = loop_video

        self.video_capture = None

        self.sct = mss.mss()

        if self.input_mode == "video_file":

            if not Path(self.video_path).exists():
                raise FileNotFoundError(f"Video file not found: {self.video_path}")

            self.video_capture = cv2.VideoCapture(self.video_path)

    """ ### SEGMENT: FRAME CAPTURE ###
    get_frame():
    Captures screen region via mss and returns BGR numpy frame (H, W, 3)."""
    def get_frame(self):
        if self.input_mode == "screen_capture":

            screenshot = self.sct.grab(self.capture_region)

            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        elif self.input_mode == "video_file":

            success, frame = self.video_capture.read()

            if not success:

                if self.loop_video:
                    self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    return self.get_frame()

                return None
        return frame

    def capture_frame(self):
        return self.get_frame()

    def go_dormant(self):
        pass
        
    def stop(self):
        self.running = False

        if self.video_capture is not None:
            self.video_capture.release()



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
