"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Defines reusable ROI (Region of Interest) configurations separate from runtime logic.

RESPONSIBILITIES:
- Provide predefined ROI layouts
- Serve as a reference or template for ROI positioning
- Keep ROI definitions modular and reusable

USED BY:
- Potentially main.py or setup workflows
- Future presets / calibration systems

INPUTS:
- None (static definitions)

OUTPUTS:
- ROI definitions (typically dict or structured format)

DESIGN INTENT:
Decouple ROI definitions from runtime logic so they can be reused,
shared, or swapped without modifying core system behavior. """

from bound_box_define import bound_box_define

""" ### SEGMENT: ROI DEFINITIONS ###
Contains predefined ROI configurations.

NOTES:
- These are not dynamically updated
- Likely used as starting points or presets
- Final ROI values used in runtime come from config_manager

IMPORTANT:
All ROI values should align with the %-based system
used throughout the application. """

class subject_roi(bound_box_define):
    def __init__(self, frame_width, frame_height):
        """
        ROI defined as percentages of the frame size.
        Adjust these values later as needed.
        """
        x_pct = 0.22
        y_pct = 0.02
        w_pct = 0.33
        h_pct = 0.42

        x = int(frame_width * x_pct)
        y = int(frame_height * y_pct)
        w = int(frame_width * w_pct)
        h = int(frame_height * h_pct)

        super().__init__(label="subject", x=x, y=y, w=w, h=h)


class object_roi(bound_box_define):
    def __init__(self, frame_width, frame_height):
        """
        ROI defined as percentages of the frame size.
        Adjust these values later as needed.
        """
        x_pct = 0.11
        y_pct = 0.50
        w_pct = 0.56
        h_pct = 0.23

        x = int(frame_width * x_pct)
        y = int(frame_height * y_pct)
        w = int(frame_width * w_pct)
        h = int(frame_height * h_pct)

        super().__init__(label="object", x=x, y=y, w=w, h=h)






"""              ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

rois.py (optional presets)
    ↓
control_panel.py (user adjusts ROI)
    ↓
config_manager.py (stores ROI as %)
    ↓
main.py (converts % → pixels per frame)

DESIGN INTENT:
Provide a flexible entry point for predefined layouts
without interfering with user-controlled ROI behavior. """
