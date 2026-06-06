"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Handles all visual rendering of overlays including ROI boxes, labels, grids, and event banners.

RESPONSIBILITIES:
- Draw ROI rectangles (subject/object)
- Render optional labels and coordinates
- Display grid and capture border
- Render current system state (event banner)

USED BY:
- main.py (overlay rendering loop)

INPUTS:
- Frame dimensions
- ROI box objects (bound_box_define)
- Labels, colors, display flags

OUTPUTS:
- RGBA overlay frame for display

DESIGN INTENT:
Keep all visualization logic isolated from detection and processing logic."""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from bound_box_define import bound_box_define


class bound_box_drawer:
    def __init__(
        self,
        default_color: Tuple[int, int, int, int] = (0, 255, 0, 255),
        capture_color: Tuple[int, int, int, int] = (0, 255, 255, 255),
        text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
        banner_bg_color: Tuple[int, int, int, int] = (40, 40, 40, 180),
        grid_color: Tuple[int, int, int, int] = (90, 90, 90, 120),
        thickness: int = 2,
        font_scale: float = 0.5,
        font_thickness: int = 1,
        banner_height: int = 50
    ):
        self.default_color = default_color
        self.capture_color = capture_color
        self.text_color = text_color
        self.banner_bg_color = banner_bg_color
        self.grid_color = grid_color
        self.thickness = thickness
        self.font_scale = font_scale
        self.font_thickness = font_thickness
        self.banner_height = banner_height
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    """         ### SEGMENT: OVERLAY CANVAS ###
    make_overlay_canvas():
    Creates a blank transparent RGBA canvas matching frame size."""
    
    def make_overlay_canvas(self, frame_width: int, frame_height: int):
        canvas = np.zeros((frame_height, frame_width, 4), dtype=np.uint8)
        return canvas

    """             ### SEGMENT: EVENT DISPLAY ###
    draw_event_banner():
    Displays current system state (e.g., Warmup, Motion Detected, Reward)."""
        
    def draw_event_banner(
        self,
        canvas,
        message: str,
        previous_session_status: str = ""
    ):
        if not message:
            message = "Idle"

        h, w = canvas.shape[:2]

        overlay = canvas.copy()
        cv2.rectangle(
            overlay,
            (0, 0),
            (w, self.banner_height),
            self.banner_bg_color,
            -1
        )

        canvas = self._alpha_blend(overlay, canvas)

        cv2.putText(
            canvas,
            message,
            (12, int(self.banner_height * 0.65)),
            self.font,
            0.7,
            self.text_color,
            2,
            cv2.LINE_AA
        )

        if previous_session_status:

            status_text = (f"Prev Session: {previous_session_status}")

            text_size = cv2.getTextSize(
                status_text,
                self.font,
                0.7,
                2
            )[0]

            cv2.putText(
                canvas,
                status_text,
                (
                    w - text_size[0] - 12,
                    int(self.banner_height * 0.65)
                ),
                self.font,
                0.7,
                self.text_color,
                2,
                cv2.LINE_AA
            )

        return canvas
        
    """             ### SEGMENT: GRID + BORDER ###
        draw_grid():
        Draws background reference grid.

        draw_capture_border():
        Draws outer boundary of capture region."""

    def draw_capture_border(self, canvas, label: str = "Capture Region"):
        h, w = canvas.shape[:2]

        top = 0 #self.banner_height
        left = 0
        right = w - 1
        bottom = h - 1

        cv2.rectangle(
            canvas,
            (left, top),
            (right, bottom),
            self.capture_color,
            self.thickness
        )

        cv2.putText(
            canvas,
            label,
            (10, top + 20),
            self.font,
            self.font_scale,
            self.capture_color,
            self.font_thickness,
            cv2.LINE_AA
        )

        self._draw_point_label(canvas, left, top, "(0,0)", self.capture_color)
        self._draw_point_label(canvas, max(0, right - 110), top, f"({right},0)", self.capture_color)
        self._draw_point_label(canvas, left, max(top + 14, bottom - 8), f"(0,{bottom - top})", self.capture_color)
        self._draw_point_label(
            canvas,
            max(0, right - 150),
            max(top + 14, bottom - 8),
            f"({right},{bottom - top})",
            self.capture_color
        )

        return canvas

    def draw_grid(self, canvas, step: int = 100):
        h, w = canvas.shape[:2]
        frame_top = 0 #self.banner_height

        for x in range(0, w, step):
            cv2.line(
                canvas,
                (x, frame_top),
                (x, h),
                self.grid_color,
                1,
                cv2.LINE_AA
            )
            cv2.putText(
                canvas,
                str(x),
                (x + 4, frame_top + 16),
                self.font,
                0.4,
                self.grid_color,
                1,
                cv2.LINE_AA
            )

        relative_y = 0
        for y in range(frame_top, h, step):
            cv2.line(
                canvas,
                (0, y),
                (w, y),
                self.grid_color,
                1,
                cv2.LINE_AA
            )
            cv2.putText(
                canvas,
                str(relative_y),
                (4, y + 16),
                self.font,
                0.4,
                self.grid_color,
                1,
                cv2.LINE_AA
            )
            relative_y += step

        return canvas

    def draw_box(
        self,
        canvas,
        box: bound_box_define,
        color: Optional[Tuple[int, int, int, int]] = None,
        label: Optional[str] = None,
        show_coords: bool = True
    ):
        clr = color if color is not None else self.default_color

        x = box.x
        y = box.y #+ self.banner_height
        w = box.w
        h = box.h

        cv2.rectangle(
            canvas,
            (x, y),
            (x + w, y + h),
            clr,
            self.thickness
        )

        if label:
            cv2.putText(
                canvas,
                label,
                (x, max(self.banner_height + 18, y - 8)),
                self.font,
                self.font_scale,
                clr,
                self.font_thickness,
                cv2.LINE_AA
            )

        if show_coords:
            top_left_text = f"({box.x},{box.y})"
            bottom_right_text = f"({box.x + box.w},{box.y + box.h})"

            self._draw_point_label(canvas, x, y, top_left_text, clr)
            self._draw_point_label(
                canvas,
                max(0, x + w - 95),
                max(self.banner_height + 14, y + h - 8),
                bottom_right_text,
                clr
            )

        return canvas

    """             ### SEGMENT: ROI DRAWING ###
    draw_boxes():
    Draws ROI rectangles with optional labels and coordinate text."""
    
    def draw_boxes(
        self,
        canvas,
        boxes: List[bound_box_define],
        labels: Optional[List[str]] = None,
        colors: Optional[List[Tuple[int, int, int, int]]] = None,
        show_coords: bool = True
    ):
        for i, box in enumerate(boxes):
            label = labels[i] if labels is not None and i < len(labels) else None
            color = colors[i] if colors and i < len(colors) else None
            self.draw_box(canvas, box, color=color, label=label, show_coords=show_coords)

        return canvas

    def _draw_point_label(self, canvas, x: int, y: int, text: str, color):
        cv2.putText(
            canvas,
            text,
            (max(0, x + 4), max(12, y - 4)),
            self.font,
            0.4,
            color,
            1,
            cv2.LINE_AA
        )

    def _alpha_blend(self, fg, bg):
        alpha = fg[:, :, 3:4] / 255.0
        out = bg.copy()
        out[:, :, :3] = (fg[:, :, :3] * alpha + bg[:, :, :3] * (1 - alpha)).astype(np.uint8)
        out[:, :, 3] = np.maximum(bg[:, :, 3], fg[:, :, 3])
        return out
        
        
        
"""                 ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

main.py
    ↓ (creates overlay frame)
bound_box_drawer.py
    ↓ (renders visual elements)
overlay_window.py
    ↓ (displays on screen)

INPUT SOURCES:
- ROI boxes from main.py
- display flags from config_manager/control_panel

DESIGN INTENT:
Ensure visual debugging and user feedback remain decoupled
from core detection and decision logic."""
