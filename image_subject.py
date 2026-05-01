"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Defines the subject image object used for storing and passing subject-frame data through the Bird Bros pipeline.

RESPONSIBILITIES:
- Represent a subject image/frame
- Store any subject-specific metadata tied to that frame
- Provide a clean handoff object between capture, analysis, and session logic

USED BY:
- main.py
- subject_session.py
- vision_api.py (directly or indirectly)

INPUTS:
- Cropped subject frame
- Any associated labels or state metadata

OUTPUTS:
- Structured subject image object for downstream processing

DESIGN INTENT:
Keep subject-frame representation separate from orchestration and analysis logic.
"""


from typing import Optional

class image_subject:
    def __init__ (
        self,
        liveLabel: Optional[str],
        hodlBool: Optional[bool],
        hodlClass: Optional[str],
        isMatch: Optional[bool]
    ) -> None:
        self.liveLabel = liveLabel  #Living Subject i.e animal, person, etc...
        self.hodlBool = hodlBool    #Boolean for if the subject is holding/carrying another object
        self.hodlClass = hodlClass  #String classification/identification of hodl
        self.isMatch = isMatch
