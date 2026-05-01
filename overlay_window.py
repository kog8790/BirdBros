"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Creates and manages the transparent overlay window used to display ROIs,
visual guides, and system state on top of the screen.

RESPONSIBILITIES:
- Initialize and manage PySide6 overlay window
- Display rendered overlay frames
- Maintain correct position and size relative to capture region

USED BY:
- main.py (visual output layer)

INPUTS:
- Overlay frames (RGBA)
- Capture region geometry

OUTPUTS:
- On-screen visual overlay

DESIGN INTENT:
Separate visualization from processing so the system can run headless or with UI.
"""

import sys
import numpy as np
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget


"""                 ### SEGMENT: OVERLAY WINDOW CLASS ###
overlay_window

STATE:
- window geometry (position + size)
- current frame buffer

BEHAVIOR:
- Creates frameless, transparent window
- Stays aligned with capture region
- Updates displayed frame in real time

IMPORTANT:
Must remain lightweight to avoid impacting frame loop performance."""
class overlay_window(QWidget):
    def __init__(self, left: int, top: int, width: int, height: int):
        super().__init__()

        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height

        self.overlay_frame = np.zeros((height, width, 4), dtype=np.uint8)

        self.setWindowTitle("Bird Bros Overlay")
        self.setGeometry(QRect(self.left, self.top, self.width_value, self.height_value))

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.show()

    """                 ### SEGMENT: FRAME UPDATE ###
    update_frame():
    Updates the displayed overlay frame."""
    
    def update_frame(self, frame_rgba: np.ndarray):
        """
        Accepts a numpy RGBA image of shape (h, w, 4), dtype uint8.
        """
        if frame_rgba is None:
            return

        if not isinstance(frame_rgba, np.ndarray):
            raise TypeError("overlay frame must be a numpy array")

        if frame_rgba.dtype != np.uint8:
            raise TypeError("overlay frame must use dtype uint8")

        if len(frame_rgba.shape) != 3 or frame_rgba.shape[2] != 4:
            raise ValueError("overlay frame must have shape (height, width, 4)")

        expected_shape = (self.height_value, self.width_value, 4)
        if frame_rgba.shape != expected_shape:
            raise ValueError(
                f"overlay frame shape {frame_rgba.shape} does not match expected {expected_shape}"
            )

        self.overlay_frame = frame_rgba.copy()
        self.update()

    def paintEvent(self, event):
        if self.overlay_frame is None:
            return

        h, w, ch = self.overlay_frame.shape
        bytes_per_line = ch * w

        image = QImage(
            self.overlay_frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGBA8888
        )

        painter = QPainter(self)
        painter.drawImage(0, 0, image)
        painter.end()

    def move_overlay(self, left: int, top: int):
        self.left = left
        self.top = top
        self.move(self.left, self.top)

    def resize_overlay(self, width: int, height: int):
        self.width_value = width
        self.height_value = height
        self.overlay_frame = np.zeros((height, width, 4), dtype=np.uint8)
        self.resize(width, height)

    """              ### SEGMENT: GEOMETRY CONTROL ###
    set_overlay_geometry():
    Adjusts overlay position and size to match capture region."""
    
    def set_overlay_geometry(self, left: int, top: int, width: int, height: int):
        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height
        self.overlay_frame = np.zeros((height, width, 4), dtype=np.uint8)
        self.setGeometry(QRect(left, top, width, height))

"""             ### SEGMENT: APPLICATION CONTEXT ###
get_or_create_qt_app():
Ensures a single Qt application instance exists for the overlay system."""

def get_or_create_qt_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app




"""                     ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

main.py
    ↓ (generates overlay_frame via bound_box_drawer)
overlay_window.update_frame()
    ↓
Qt window renders overlay on screen

DESIGN INTENT:
Act as the final presentation layer without introducing processing logic."""
