"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Creates and manages the transparent overlay window used to display ROIs,
visual guides, and system state on top of the screen.

RESPONSIBILITIES:
- Initialize and manage PySide6 overlay window
- Display rendered overlay frames
- Maintain correct position and size relative to capture region
- Host live region editing interaction when provided by main.py

USED BY:
- main.py (visual output layer)

INPUTS:
- Overlay frames (RGBA)
- Capture region geometry
- Optional LiveRegionInteraction object

OUTPUTS:
- On-screen visual overlay
- Optional live region edit commit signal

DESIGN INTENT:
Separate visualization from processing so the system can run headless or with UI.
"""

import sys
from time import monotonic

import cv2
import numpy as np
from PySide6.QtCore import Qt, QRect, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QApplication, QWidget

from capture_regions import CaptureRegion
from draw_regions import CAPTURE_TARGET_KEY, LiveRegionInteraction
from mouse_tools import MouseHoverLock

try:
    from AppKit import NSCursor
except Exception:
    NSCursor = None


"""                 ### SEGMENT: OVERLAY WINDOW CLASS ###
overlay_window

STATE:
- window geometry (position + size)
- current frame buffer
- optional live region interaction controller
- mouse pass-through state

BEHAVIOR:
- Creates frameless, transparent window
- Stays aligned with capture region
- Updates displayed frame in real time
- Can temporarily become mouse-interactive when cursor nears editable regions

IMPORTANT:
Must remain lightweight to avoid impacting frame loop performance."""
class overlay_window(QWidget):
    region_edit_committed = Signal(object)

    def __init__(self, left: int, top: int, width: int, height: int):
        super().__init__()

        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height
        self._interaction_padding = 0

        self.overlay_frame = np.zeros((height, width, 4), dtype=np.uint8)

        self.region_interaction = None
        self._mouse_passthrough = True
        self._hover_poll_interval_ms = 33
        self._hover_release_misses_required = 4
        self._hover_release_misses = 0
        self._hover_lock_duration_s = 0.25
        self._hover_lock = None
        self._cursor_role = "default"
        self._using_override_cursor = False

        self.setWindowTitle("Bird Bros Overlay")
        self._apply_native_overlay_geometry()

        # The overlay starts as a visual guide, not a control surface.
        # It becomes interactive only while the cursor is near an editable region
        # or while a region drag is in progress.
        self.setWindowFlags(
            Qt.Window |
            Qt.Tool |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowDoesNotAcceptFocus
        )

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMouseTracking(True)

        self._hover_timer = QTimer(self)
        self._hover_timer.timeout.connect(self._poll_region_hover)
        self._hover_timer.start(self._hover_poll_interval_ms)

        self.show()

    """                 ### SEGMENT: LIVE REGION INTERACTION ###
    set_live_region_interaction():
    Attaches a live region interaction controller supplied by main.py."""

    def set_live_region_interaction(self, interaction: LiveRegionInteraction | None):
        self.region_interaction = interaction

        if self.region_interaction is None:
            self._hover_lock = None
            self._clear_region_cursor()
            self._set_mouse_passthrough(True)
            self.update()
            return

        self._poll_region_hover()
        self.update()

    def clear_live_region_interaction(self):
        self.set_live_region_interaction(None)

    def _poll_region_hover(self):
        if self.region_interaction is None:
            return

        if self.region_interaction.is_dragging:
            self._set_mouse_passthrough(False)
            return

        pos = QCursor.pos()
        hover = self.region_interaction.hover_at_screen_point(
            int(pos.x()),
            int(pos.y()),
        )

        now = monotonic()

        if hover.has_target:
            self._hover_release_misses = 0
            self._hover_lock = MouseHoverLock.create(
                payload=hover,
                now=now,
                duration_s=self._hover_lock_duration_s,
            )
            self._set_mouse_passthrough(False)
            self._set_cursor_from_role(hover.cursor_role)
        else:
            if self._hover_lock is not None and self._hover_lock.is_valid(now):
                self._set_mouse_passthrough(False)
                self.update()
                return

            self._hover_lock = None
            self._hover_release_misses += 1

            if self._hover_release_misses >= self._hover_release_misses_required:
                self._hover_release_misses = 0
                self._clear_region_cursor()
                self._set_mouse_passthrough(True)

        self.update()

    def _set_mouse_passthrough(self, enabled: bool):
        if self._mouse_passthrough == enabled:
            return

        self._mouse_passthrough = enabled

        # Experiment:
        # Keep native window flags stable after show().
        # Only toggle Qt-level mouse routing.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)

    def _set_cursor_from_role(self, cursor_role: str):
        cursor_map = {
            "default": Qt.ArrowCursor,
            "move": Qt.SizeAllCursor,
            "resize_horizontal": Qt.SizeHorCursor,
            "resize_vertical": Qt.SizeVerCursor,
            "resize_diagonal_forward": Qt.SizeBDiagCursor,
            "resize_diagonal_backward": Qt.SizeFDiagCursor,
        }

        cursor_shape = cursor_map.get(cursor_role, Qt.ArrowCursor)
        cursor = QCursor(cursor_shape)

        self.setCursor(cursor)

        if self._using_override_cursor:
            QApplication.changeOverrideCursor(cursor)
        else:
            QApplication.setOverrideCursor(cursor)
            self._using_override_cursor = True

        self._set_native_cursor_from_role(cursor_role)
        self._cursor_role = cursor_role

    def _set_native_cursor_from_role(self, cursor_role: str):
        if NSCursor is None:
            return

        if cursor_role == "resize_horizontal":
            NSCursor.resizeLeftRightCursor().set()
            return

        if cursor_role == "resize_vertical":
            NSCursor.resizeUpDownCursor().set()
            return

        if cursor_role in {
            "resize_diagonal_forward",
            "resize_diagonal_backward",
        }:
            # Qt provides diagonal resize cursors. AppKit does not expose
            # public diagonal resize cursors, so do not override Qt's cursor
            # with a horizontal native fallback here.
            return

        if cursor_role == "move":
            NSCursor.openHandCursor().set()
            return

        NSCursor.arrowCursor().set()

    def _clear_region_cursor(self):
        if self._cursor_role == "default" and not self._using_override_cursor:
            return

        self._cursor_role = "default"
        self.unsetCursor()

        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

        self._using_override_cursor = False

        if NSCursor is not None:
            NSCursor.arrowCursor().set()

    def _global_point_from_event(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()

        return event.globalPos()

    def mousePressEvent(self, event):
        if (
            self.region_interaction is None
            or event.button() != Qt.LeftButton
        ):
            super().mousePressEvent(event)
            return

        point = self._global_point_from_event(event)
        x = int(point.x())
        y = int(point.y())

        now = monotonic()
        locked_hover = None

        if self._hover_lock is not None and self._hover_lock.is_valid(now):
            locked_hover = self._hover_lock.payload

        if locked_hover is not None and locked_hover.has_target:
            drag = self.region_interaction.begin_drag_from_hover(
                locked_hover,
                x,
                y,
            )
        else:
            drag = self.region_interaction.begin_drag_at_screen_point(x, y)

        if drag is None:
            super().mousePressEvent(event)
            return

        self._hover_lock = None
        self._hover_release_misses = 0
        self._set_mouse_passthrough(False)
        self._set_cursor_from_role(self.region_interaction.hover.cursor_role)
        event.accept()
        self.update()

    def mouseMoveEvent(self, event):
        if self.region_interaction is None:
            super().mouseMoveEvent(event)
            return

        point = self._global_point_from_event(event)

        if self.region_interaction.is_dragging:
            preview = self.region_interaction.drag_to_screen_point(
                int(point.x()),
                int(point.y()),
            )

            self._apply_live_capture_preview_geometry(preview)

            event.accept()
            self.update()
            return

        hover = self.region_interaction.hover_at_screen_point(
            int(point.x()),
            int(point.y()),
        )

        if hover.has_target:
            self._set_cursor_from_role(hover.cursor_role)
        else:
            self._clear_region_cursor()

        event.accept()
        self.update()

    def _apply_live_capture_preview_geometry(self, preview):
        if preview is None or preview.drag is None:
            return

        if preview.drag.target_key != CAPTURE_TARGET_KEY:
            return

        capture_rect = preview.capture_rect

        self.set_overlay_geometry(
            left=int(capture_rect.x),
            top=int(capture_rect.y),
            width=int(capture_rect.width),
            height=int(capture_rect.height),
        )

    def mouseReleaseEvent(self, event):
        if (
            self.region_interaction is None
            or event.button() != Qt.LeftButton
            or not self.region_interaction.is_dragging
        ):
            super().mouseReleaseEvent(event)
            return

        result = self.region_interaction.finish_drag()

        if result is not None:
            self.region_edit_committed.emit(result)

        event.accept()
        self._poll_region_hover()
        self.update()

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key_Escape
            and self.region_interaction is not None
            and self.region_interaction.is_dragging
        ):
            was_capture_drag = (
                self.region_interaction.drag is not None
                and self.region_interaction.drag.target_key == CAPTURE_TARGET_KEY
            )

            self.region_interaction.cancel_drag()

            if was_capture_drag:
                state = self.region_interaction.get_preview_state()
                capture_rect = state.capture_rect
                self.set_overlay_geometry(
                    left=int(capture_rect.x),
                    top=int(capture_rect.y),
                    width=int(capture_rect.width),
                    height=int(capture_rect.height),
                )

            self._poll_region_hover()
            event.accept()
            self.update()
            return

        super().keyPressEvent(event)

    """                 ### SEGMENT: FRAME UPDATE ###
    update_frame():
    Updates the displayed overlay frame."""

    def update_frame(self, frame_rgba: np.ndarray):
        """
        Accepts a numpy RGBA image of shape (h, w, 4), dtype uint8.
        Resizes display input to current overlay geometry instead of crashing.
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
            frame_rgba = cv2.resize(
                frame_rgba,
                (self.width_value, self.height_value),
                interpolation=cv2.INTER_NEAREST
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
        painter.drawImage(
            self._interaction_padding,
            self._interaction_padding,
            image,
        )
        self._paint_region_interaction_preview(painter)
        painter.end()

    def _roi_preview_color_for_key(self, key):
        if self.region_interaction is None:
            return QColor(255, 255, 255, 230)

        roi = self.region_interaction.preview_roi_by_key(key)

        if roi is None:
            return QColor(255, 255, 255, 230)

        if roi.is_subject:
            return QColor(0, 255, 0, 230)

        if roi.is_trigger or roi.is_object:
            return QColor(255, 0, 0, 230)

        return QColor(255, 255, 255, 230)

    def _paint_region_interaction_preview(self, painter):
        if self.region_interaction is None:
            return

        state = self.region_interaction.get_preview_state()

        painter.setRenderHint(QPainter.Antialiasing)

        # Capture Region preview drawing is intentionally disabled.
        # During capture resize, the capture region must be represented by the
        # actual overlay window geometry, not by a second painted rectangle.
        for key, rect in state.roi_rects.items():
            local_rect = self._screen_rect_to_local_qrect(rect)
            roi_color = self._roi_preview_color_for_key(key)

            roi_pen = QPen(roi_color)
            roi_pen.setWidth(3)

            painter.setPen(roi_pen)
            painter.drawRect(local_rect)

            if key == state.hover.target_key:
                hover_pen = QPen(roi_color)
                hover_pen.setWidth(2)
                hover_pen.setStyle(Qt.DotLine)
                painter.setPen(hover_pen)
                painter.drawRect(local_rect.adjusted(-3, -3, 3, 3))

            self._paint_resize_handles(painter, local_rect)

    def _paint_resize_handles(self, painter, rect):
        handle_size = 7
        half = handle_size // 2

        points = [
            rect.topLeft(),
            rect.topRight(),
            rect.bottomLeft(),
            rect.bottomRight(),
        ]

        for point in points:
            painter.fillRect(
                QRect(
                    point.x() - half,
                    point.y() - half,
                    handle_size,
                    handle_size,
                ),
                QColor(255, 255, 255, 230),
            )

    def _screen_rect_to_local_qrect(self, rect):
        return QRect(
            int(rect.x - self.left + self._interaction_padding),
            int(rect.y - self.top + self._interaction_padding),
            int(rect.width),
            int(rect.height),
        )

    def move_overlay(self, left: int, top: int):
        self.set_overlay_geometry(
            left=left,
            top=top,
            width=self.width_value,
            height=self.height_value,
        )

    def resize_overlay(self, width: int, height: int):
        self.set_overlay_geometry(
            left=self.left,
            top=self.top,
            width=width,
            height=height,
        )

    def _current_capture_region(self) -> CaptureRegion:
        return CaptureRegion(
            left=int(self.left),
            top=int(self.top),
            width=int(self.width_value),
            height=int(self.height_value),
        )

    def _apply_native_overlay_geometry(self):
        capture_region = self._current_capture_region()
        self._interaction_padding = capture_region.interaction_padding_px()

        expanded_region = capture_region.expanded_for_interaction()
        self.setGeometry(
            QRect(
                int(expanded_region.left),
                int(expanded_region.top),
                int(expanded_region.width),
                int(expanded_region.height),
            )
        )

    """              ### SEGMENT: GEOMETRY CONTROL ###
    set_overlay_geometry():
    Adjusts overlay position and size to match capture region.

    The visible Capture Region remains left/top/width/height. The native
    QWidget is expanded invisibly around it so outside-edge resize grabs can
    still be delivered to BirdBros."""

    def set_overlay_geometry(self, left: int, top: int, width: int, height: int):
        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height
        self.overlay_frame = np.zeros((height, width, 4), dtype=np.uint8)
        self._apply_native_overlay_geometry()

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
