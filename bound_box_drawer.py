""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Handles all visual rendering of overlays including ROI boxes, labels, grids, and capture border.

RESPONSIBILITIES:
- Draw ROI rectangles
- Render optional labels and coordinates
- Display grid and capture border
- Keep overlay visuals separate from detection logic

DESIGN INTENT:
Make the live overlay feel like a polished instrument layer instead of a debug utility.
"""

import cv2
import numpy as np
from typing import List, Optional, Tuple
from bound_box_define import bound_box_define


class bound_box_drawer:
    def __init__(
        self,
        default_color: Tuple[int, int, int, int] = (105, 236, 198, 235),
        capture_color: Tuple[int, int, int, int] = (0, 214, 235, 220),
        text_color: Tuple[int, int, int, int] = (248, 243, 231, 245),
        banner_bg_color: Tuple[int, int, int, int] = (20, 22, 24, 185),
        grid_color: Tuple[int, int, int, int] = (248, 243, 231, 42),
        thickness: int = 2,
        font_scale: float = 0.52,
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

        self.label_bg_color = (12, 14, 16, 165)
        self.coordinate_bg_color = (12, 14, 16, 120)
        self.corner_length = 18

    # ================================
    # OVERLAY CANVAS
    # ================================

    def make_overlay_canvas(self, frame_width: int, frame_height: int):
        return np.zeros((frame_height, frame_width, 4), dtype=np.uint8)

    # ================================
    # EVENT DISPLAY
    # Kept for backward compatibility; main.py no longer needs this because
    # status_window.py owns runtime status.
    # ================================

    def draw_event_banner(
        self,
        canvas,
        message: str,
        previous_session_status: str = ""
    ):
        if not message:
            message = "Idle"

        h, w = canvas.shape[:2]

        self._draw_rounded_rect(
            canvas,
            8,
            8,
            w - 8,
            min(h - 8, self.banner_height),
            self.banner_bg_color,
            radius=14,
            fill=True
        )

        self._draw_label_with_backing(
            canvas,
            message,
            18,
            31,
            self.text_color,
            bg_color=(0, 0, 0, 0),
            scale=0.64,
            thickness=2
        )

        if previous_session_status:
            status_text = f"Prev Session: {previous_session_status}"
            text_size = cv2.getTextSize(status_text, self.font, 0.64, 2)[0]
            self._draw_label_with_backing(
                canvas,
                status_text,
                w - text_size[0] - 24,
                31,
                self.text_color,
                bg_color=(0, 0, 0, 0),
                scale=0.64,
                thickness=2
            )

        return canvas

    # ================================
    # GRID + BORDER
    # ================================

    def draw_capture_border(self, canvas, label: str = "Capture Region"):
        h, w = canvas.shape[:2]

        left = 0
        top = 0
        right = w - 1
        bottom = h - 1

        self._draw_outline(canvas, left, top, right, bottom, self.capture_color, self.thickness)
        self._draw_corner_accents(canvas, left, top, right, bottom, self.capture_color)

        self._draw_label_with_backing(
            canvas,
            label,
            12,
            24,
            self.capture_color,
            bg_color=self.label_bg_color,
            scale=self.font_scale,
            thickness=self.font_thickness
        )

        self._draw_point_label(canvas, left, top, "(0,0)", self.capture_color)
        self._draw_point_label(canvas, max(0, right - 82), top, f"({right},0)", self.capture_color)
        self._draw_point_label(canvas, left, max(16, bottom - 8), f"(0,{bottom})", self.capture_color)
        self._draw_point_label(
            canvas,
            max(0, right - 104),
            max(16, bottom - 8),
            f"({right},{bottom})",
            self.capture_color
        )

        return canvas

    def draw_grid(self, canvas, step: int = 100):
        h, w = canvas.shape[:2]

        for x in range(0, w, step):
            cv2.line(canvas, (x, 0), (x, h), self.grid_color, 1, cv2.LINE_AA)

        for y in range(0, h, step):
            cv2.line(canvas, (0, y), (w, y), self.grid_color, 1, cv2.LINE_AA)

        return canvas

    # ================================
    # ROI DRAWING
    # ================================

    def draw_box(
        self,
        canvas,
        box: bound_box_define,
        color: Optional[Tuple[int, int, int, int]] = None,
        label: Optional[str] = None,
        show_coords: bool = True
    ):
        clr = color if color is not None else self.default_color

        x = int(box.x)
        y = int(box.y)
        w = int(box.w)
        h = int(box.h)

        right = x + w
        bottom = y + h

        self._draw_outline(canvas, x, y, right, bottom, clr, self.thickness)
        self._draw_corner_accents(canvas, x, y, right, bottom, clr)

        if label:
            label_y = max(24, y - 8)
            self._draw_label_with_backing(
                canvas,
                label,
                x,
                label_y,
                clr,
                bg_color=self.label_bg_color,
                scale=self.font_scale,
                thickness=self.font_thickness
            )

        if show_coords:
            top_left_text = f"({box.x},{box.y})"
            bottom_right_text = f"({box.x + box.w},{box.y + box.h})"

            self._draw_point_label(canvas, x, y, top_left_text, clr)
            self._draw_point_label(
                canvas,
                max(0, right - 84),
                max(16, bottom - 8),
                bottom_right_text,
                clr
            )

        return canvas

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

    # ================================
    # DRAWING HELPERS
    # ================================

    def _draw_outline(self, canvas, left, top, right, bottom, color, thickness):
        cv2.rectangle(
            canvas,
            (int(left), int(top)),
            (int(right), int(bottom)),
            color,
            max(1, thickness),
            cv2.LINE_AA
        )

    def _draw_corner_accents(self, canvas, left, top, right, bottom, color):
        length = min(self.corner_length, max(8, int((right - left) * 0.18)), max(8, int((bottom - top) * 0.18)))
        accent_thickness = max(2, self.thickness + 1)

        points = [
            ((left, top), (left + length, top)),
            ((left, top), (left, top + length)),
            ((right, top), (right - length, top)),
            ((right, top), (right, top + length)),
            ((left, bottom), (left + length, bottom)),
            ((left, bottom), (left, bottom - length)),
            ((right, bottom), (right - length, bottom)),
            ((right, bottom), (right, bottom - length)),
        ]

        for start, end in points:
            cv2.line(canvas, start, end, color, accent_thickness, cv2.LINE_AA)

    def _draw_label_with_backing(
        self,
        canvas,
        text: str,
        x: int,
        y: int,
        color,
        bg_color=None,
        scale=None,
        thickness=None
    ):
        if not text:
            return

        scale = self.font_scale if scale is None else scale
        thickness = self.font_thickness if thickness is None else thickness
        bg_color = self.label_bg_color if bg_color is None else bg_color

        text_size, baseline = cv2.getTextSize(text, self.font, scale, thickness)
        text_w, text_h = text_size

        pad_x = 7
        pad_y = 5

        x1 = max(0, int(x) - pad_x)
        y1 = max(0, int(y) - text_h - pad_y)
        x2 = min(canvas.shape[1] - 1, int(x) + text_w + pad_x)
        y2 = min(canvas.shape[0] - 1, int(y) + baseline + pad_y)

        if bg_color[3] > 0:
            self._draw_rounded_rect(canvas, x1, y1, x2, y2, bg_color, radius=7, fill=True)

        cv2.putText(
            canvas,
            text,
            (int(x), int(y)),
            self.font,
            scale,
            color,
            thickness,
            cv2.LINE_AA
        )

    def _draw_point_label(self, canvas, x: int, y: int, text: str, color):
        self._draw_label_with_backing(
            canvas,
            text,
            max(4, int(x) + 4),
            max(15, int(y) + 15),
            color,
            bg_color=self.coordinate_bg_color,
            scale=0.40,
            thickness=1
        )

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, color, radius=8, fill=True):
        x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
        radius = max(0, min(radius, abs(x2 - x1) // 2, abs(y2 - y1) // 2))
        thickness = -1 if fill else self.thickness

        if radius <= 0:
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
            return

        cv2.rectangle(canvas, (x1 + radius, y1), (x2 - radius, y2), color, thickness, cv2.LINE_AA)
        cv2.rectangle(canvas, (x1, y1 + radius), (x2, y2 - radius), color, thickness, cv2.LINE_AA)

        cv2.circle(canvas, (x1 + radius, y1 + radius), radius, color, thickness, cv2.LINE_AA)
        cv2.circle(canvas, (x2 - radius, y1 + radius), radius, color, thickness, cv2.LINE_AA)
        cv2.circle(canvas, (x1 + radius, y2 - radius), radius, color, thickness, cv2.LINE_AA)
        cv2.circle(canvas, (x2 - radius, y2 - radius), radius, color, thickness, cv2.LINE_AA)

    def _alpha_blend(self, fg, bg):
        alpha = fg[:, :, 3:4] / 255.0
        out = bg.copy()
        out[:, :, :3] = (fg[:, :, :3] * alpha + bg[:, :, :3] * (1 - alpha)).astype(np.uint8)
        out[:, :, 3] = np.maximum(bg[:, :, 3], fg[:, :, 3])
        return out


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
main.py
    ↓ creates overlay frame
bound_box_drawer.py
    ↓ renders visual elements
overlay_window.py
    ↓ displays on screen

DESIGN INTENT:
The overlay should support confidence and tuning without making the app feel like a lab bench.
"""

