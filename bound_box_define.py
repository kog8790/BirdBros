"""
PURPOSE:
Defines a simple ROI container used across the system to represent rectangular regions.

STRUCTURE:
- Stores x, y, w, h, and optional label
- No internal logic, validation, or transformations
- Acts as a passive data object

USAGE:
- Instantiated in main.py after ROI % → pixel conversion
- Passed into:
  - cropping functions
  - overlay rendering (bound_box_drawer)
  - motion detection pipeline (indirectly via crops)

INPUTS:
- Pixel-based coordinates relative to capture region

OUTPUTS:
- Object with accessible attributes: .x, .y, .w, .h, .label

DESIGN INTENT:
Keeps ROI representation isolated and dumb so all coordinate logic lives in main.py
"""

class bound_box_define:
    def __init__(self, x: int, y: int, w: int, h: int, label: str = None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.label = label

    def as_tuple(self):
        return (self.x, self.y, self.w, self.h)

    def area(self):
        return self.w * self.h

    def bottom_right(self):
        return (self.x + self.w, self.y + self.h)

    def contains(self, px: int, py: int) -> bool:
        return (
            self.x <= px <= self.x + self.w and
            self.y <= py <= self.y + self.h
        )

    def __repr__(self):
        return f"bound_box_define(x={self.x}, y={self.y}, w={self.w}, h={self.h}, label={self.label})"



"""
HOW THIS FITS INTO THE SYSTEM

FLOW:

control_panel.py
    ↓ (user sets ROI in pixels → saved as %)
config_manager.py
    ↓ (stores normalized ROI values)
main.py
    ↓ (% → pixel conversion per frame)
bound_box_define ← YOU ARE HERE
    ↓
crop_from_box(frame, box)
    ↓
motion_detector / vision_api / storyboard

AND ALSO:
bound_box_define → bound_box_drawer → overlay visualization
"""
