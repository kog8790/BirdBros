""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Builds a contact sheet (grid image) from a sequence of frames.

RESPONSIBILITIES:
- Accept ordered frames (time sequence)
- Resize frames to consistent dimensions
- Arrange frames into grid (left→right, top→bottom)
- Optionally annotate frame indices
- Return final image for API consumption

USED BY:
- main.py
- event_session.py (frame selection output)

DESIGN INTENT:
Provide temporal context to AI by packaging multiple frames into a single image.
"""


import cv2
import math


class contact_sheet_builder:
    def __init__(self, cell_width=200, cell_height=200, padding=5, show_index=True):
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.padding = padding
        self.show_index = show_index

    """ ### SEGMENT: BUILD ###
    build():
    frames: list of dicts OR list of raw frames
    returns: contact sheet image
    """
    def build(self, frames):
        if not frames:
            raise ValueError("No frames provided to contact sheet builder")

        # Normalize input (allow dict or raw frame)
        normalized_frames = []
        for item in frames:
            if isinstance(item, dict):
                normalized_frames.append(item.get("frame") or item.get("combined_frame"))
            else:
                normalized_frames.append(item)

        total_frames = len(normalized_frames)

        # Determine grid size (rough square)
        cols = math.ceil(math.sqrt(total_frames))
        rows = math.ceil(total_frames / cols)

        sheet_width = cols * self.cell_width + (cols - 1) * self.padding
        sheet_height = rows * self.cell_height + (rows - 1) * self.padding

        contact_sheet = self._create_canvas(sheet_width, sheet_height)

        for idx, frame in enumerate(normalized_frames):
            if frame is None:
                continue

            resized = cv2.resize(frame, (self.cell_width, self.cell_height))

            row = idx // cols
            col = idx % cols

            x = col * (self.cell_width + self.padding)
            y = row * (self.cell_height + self.padding)

            contact_sheet[y:y + self.cell_height, x:x + self.cell_width] = resized

            if self.show_index:
                self._draw_index(contact_sheet, idx + 1, x, y)

        return contact_sheet

    """ ### SEGMENT: CANVAS ###
    """
    def _create_canvas(self, width, height):
        return 255 * np.ones((height, width, 3), dtype="uint8")

    """ ### SEGMENT: INDEX DRAWING ###
    """
    def _draw_index(self, image, index, x, y):
        text = str(index)

        cv2.putText(
            image,
            text,
            (x + 5, y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
            cv2.LINE_AA
        )


import numpy as np


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

event_session → selected frames (ordered)
    ↓
contact_sheet_builder.build(frames)
    ↓
contact_sheet_image
    ↓
vision_api (single API call)

DESIGN INTENT:
Transform time-series data into spatial representation so AI can reason about motion and sequence.
"""
