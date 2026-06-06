""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Builds a contact sheet (grid image) from a sequence of selected frames.

RESPONSIBILITIES:
- Accept ordered frames as raw images or event-session record dictionaries
- Preserve the selected temporal order
- Resize frames consistently without distorting aspect ratio by default
- Arrange frames into a grid left-to-right, top-to-bottom
- Annotate frame indices for OpenAI bestFrameIndex references
- Optionally annotate lightweight debug tags during tuning
- Return final image for API consumption

DESIGN INTENT:
Selection intelligence belongs in event_session.py.
This class should only present the selected story clearly and safely.
"""

import math

import cv2
import numpy as np


class contact_sheet_builder:
    def __init__(
        self,
        cell_width=200,
        cell_height=200,
        padding=5,
        show_index=True,
        preserve_aspect_ratio=True,
        show_frame_tags=False,
        background_color=(255, 255, 255)
    ):
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.padding = padding
        self.show_index = show_index
        self.preserve_aspect_ratio = preserve_aspect_ratio
        self.show_frame_tags = show_frame_tags
        self.background_color = background_color

    # ================================
    # BUILD
    # ================================

    def build(self, frames):
        """
        frames may be:
        - list of raw OpenCV frames
        - list of dictionaries containing "frame" or "combined_frame"

        returns:
        - OpenCV BGR contact sheet image
        """
        entries = self._normalize_entries(frames)

        if not entries:
            raise ValueError("No valid frames provided to contact sheet builder")

        total_frames = len(entries)

        cols = math.ceil(math.sqrt(total_frames))
        rows = math.ceil(total_frames / cols)

        sheet_width = cols * self.cell_width + (cols - 1) * self.padding
        sheet_height = rows * self.cell_height + (rows - 1) * self.padding

        contact_sheet = self._create_canvas(sheet_width, sheet_height)

        for idx, entry in enumerate(entries):
            prepared = self._prepare_frame(entry["frame"])

            row = idx // cols
            col = idx % cols

            x = col * (self.cell_width + self.padding)
            y = row * (self.cell_height + self.padding)

            contact_sheet[y:y + self.cell_height, x:x + self.cell_width] = prepared

            if self.show_index:
                self._draw_index(contact_sheet, idx + 1, x, y)

            if self.show_frame_tags:
                tag = self._build_debug_tag(entry["metadata"])
                if tag:
                    self._draw_tag(contact_sheet, tag, x, y)

        return contact_sheet

    # ================================
    # INPUT NORMALIZATION
    # ================================

    def _normalize_entries(self, frames):
        if not frames:
            return []

        entries = []

        for item in frames:
            frame = None
            metadata = {}

            if isinstance(item, dict):
                # Do not use `a or b` with numpy arrays; array truthiness is ambiguous.
                frame = item.get("frame")

                if frame is None:
                    frame = item.get("combined_frame")

                metadata = item
            else:
                frame = item

            if self._is_valid_frame(frame):
                entries.append({
                    "frame": frame,
                    "metadata": metadata
                })

        return entries

    def _is_valid_frame(self, frame):
        return (
            frame is not None
            and hasattr(frame, "size")
            and frame.size > 0
            and len(frame.shape) in (2, 3)
        )

    # ================================
    # FRAME PREP
    # ================================

    def _prepare_frame(self, frame):
        frame = self._ensure_bgr(frame)

        if not self.preserve_aspect_ratio:
            return cv2.resize(
                frame,
                (self.cell_width, self.cell_height),
                interpolation=cv2.INTER_AREA
            )

        return self._fit_frame_to_cell(frame)

    def _ensure_bgr(self, frame):
        if len(frame.shape) == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        return frame.copy()

    def _fit_frame_to_cell(self, frame):
        frame_height, frame_width = frame.shape[:2]

        if frame_width <= 0 or frame_height <= 0:
            return self._create_canvas(self.cell_width, self.cell_height)

        scale = min(
            self.cell_width / float(frame_width),
            self.cell_height / float(frame_height)
        )

        new_width = max(1, int(frame_width * scale))
        new_height = max(1, int(frame_height * scale))

        resized = cv2.resize(
            frame,
            (new_width, new_height),
            interpolation=cv2.INTER_AREA
        )

        cell = self._create_canvas(self.cell_width, self.cell_height)

        x_offset = (self.cell_width - new_width) // 2
        y_offset = (self.cell_height - new_height) // 2

        cell[
            y_offset:y_offset + new_height,
            x_offset:x_offset + new_width
        ] = resized

        return cell

    # ================================
    # CANVAS
    # ================================

    def _create_canvas(self, width, height):
        return np.full(
            (height, width, 3),
            self.background_color,
            dtype=np.uint8
        )

    # ================================
    # INDEX / TAG DRAWING
    # ================================

    def _draw_index(self, image, index, x, y):
        text = str(index)

        cv2.rectangle(
            image,
            (x + 4, y + 4),
            (x + 34, y + 28),
            (255, 255, 255),
            -1
        )

        cv2.rectangle(
            image,
            (x + 4, y + 4),
            (x + 34, y + 28),
            (0, 0, 0),
            1
        )

        cv2.putText(
            image,
            text,
            (x + 9, y + 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            2,
            cv2.LINE_AA
        )

    def _draw_tag(self, image, tag, x, y):
        text = str(tag)[:28]

        text_size, _ = cv2.getTextSize(
            text,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            1
        )

        text_width, text_height = text_size

        label_x1 = x + 4
        label_y1 = y + self.cell_height - text_height - 12
        label_x2 = min(x + self.cell_width - 4, label_x1 + text_width + 8)
        label_y2 = y + self.cell_height - 4

        cv2.rectangle(
            image,
            (label_x1, label_y1),
            (label_x2, label_y2),
            (255, 255, 255),
            -1
        )

        cv2.rectangle(
            image,
            (label_x1, label_y1),
            (label_x2, label_y2),
            (0, 0, 0),
            1
        )

        cv2.putText(
            image,
            text,
            (label_x1 + 4, label_y2 - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 0, 0),
            1,
            cv2.LINE_AA
        )

    def _build_debug_tag(self, metadata):
        if not metadata:
            return None

        tags = []

        source = metadata.get("source")
        if source:
            tags.append(str(source))

        if metadata.get("is_roi_novel"):
            tags.append("roi")

        if metadata.get("is_scene_novel"):
            tags.append("scene")

        if metadata.get("is_regionally_novel"):
            tags.append("region")

        if metadata.get("motion_detected"):
            tags.append("motion")

        if metadata.get("centroid") is not None:
            tags.append("centroid")

        # Keep tags small so they do not crowd the API input.
        return "/".join(tags[:3]) if tags else None


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

event_session.py selects ordered behavior-relevant records
    ↓
contact_sheet_builder.build(records)
    ↓
contact_sheet_image
    ↓
vision_api receives one image containing the selected story

DESIGN INTENT:
This file formats selected frames.
It should not decide which behavior matters or which frames are important.
"""

