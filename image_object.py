"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Defines the object image used for representing frames from the receptacle/object ROI.

RESPONSIBILITIES:
- Store object-frame image data
- Carry metadata related to detected or expected objects
- Provide a structured handoff between capture, validation, and reward logic

USED BY:
- main.py
- object validation logic (vision_api / receptacle_validation)

INPUTS:
- Cropped object frame
- Expected label (from subject analysis)

OUTPUTS:
- Structured object image data for validation

DESIGN INTENT:
Keep object-frame representation modular and separate from detection and decision logic.                                                        """

from typing import Optional

class image_object:
    def __init__(
        self,
        objectLabel: Optional[str],
        isMatch: Optional[bool],
        actionLabel: Optional[str] = None
    ) -> None:
        self.objectLabel = objectLabel  # Classification of object found in the object area
        self.isMatch = isMatch          # Boolean: does this match what the subject was holding
        self.actionLabel = actionLabel  # e.g., "falling", "entered from above"
