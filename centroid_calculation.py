"""                 ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Provides centroid calculation utilities for tracking motion position within a frame.

RESPONSIBILITIES:
- Compute centroid from contours or pixel regions
- Support motion analysis and directional tracking

USED BY:
- motion_analysis (or similar logic)
- any component needing position tracking

INPUTS:
- Contours or binary masks

OUTPUTS:
- (x, y) centroid coordinates

DESIGN INTENT:
Keep geometric calculations isolated and reusable across motion-related modules.
"""

import cv2
import numpy as np
from typing import Tuple, Optional

class centroid_calculation:
    @staticmethod
    def from_bbox(bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        """
        Calculates the centroid of a rectangular bounding box.

        Args:
            bbox: A tuple (x, y, w, h)

        Returns:
            (center_x, center_y)
        """
        x, y, w, h = bbox
        center_x = x + w // 2
        center_y = y + h // 2
        return center_x, center_y

    @staticmethod
    def from_contour(contour: np.ndarray) -> Optional[Tuple[int, int]]:
        """
        Calculates the centroid of a contour using image moments.

        Args:
            contour: A NumPy array representing a single contour

        Returns:
            (center_x, center_y) if valid, otherwise None
        """
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return None
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return cx, cy

