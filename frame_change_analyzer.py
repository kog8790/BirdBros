""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Measures visual change between frames so event sessions can be guided by
meaningful scene novelty instead of only centroid trajectory.

CORE IDEA:
- ROI motion starts attention.
- Whole-frame change keeps the broader behavioral story alive.
- Centroid motion can boost frame importance, but should not be the gatekeeper.
"""

import cv2
import numpy as np


class frame_change_analyzer:
    def __init__(
        self,
        resize_width=160,
        pixel_change_threshold=25,
        scene_novelty_threshold=0.020,
        roi_novelty_threshold=0.030,
        regional_novelty_threshold=0.025,
        grid_rows=3,
        grid_cols=3
    ):
        self.resize_width = resize_width
        self.pixel_change_threshold = pixel_change_threshold

        self.scene_novelty_threshold = scene_novelty_threshold
        self.roi_novelty_threshold = roi_novelty_threshold
        self.regional_novelty_threshold = regional_novelty_threshold

        self.grid_rows = grid_rows
        self.grid_cols = grid_cols

        self.previous_scene = None
        self.previous_roi = None

    def reset(self):
        self.previous_scene = None
        self.previous_roi = None

    def analyze(self, combined_frame, object_frame=None):
        scene_gray = self._prepare_gray(combined_frame)
        roi_gray = self._prepare_gray(object_frame) if object_frame is not None else None

        if scene_gray is None:
            return self._empty_result()

        scene_metrics = self._delta_metrics(self.previous_scene, scene_gray)
        roi_metrics = self._delta_metrics(self.previous_roi, roi_gray) if roi_gray is not None else self._empty_delta()
        regional_metrics = self._regional_metrics(self.previous_scene, scene_gray)

        scene_delta = scene_metrics["delta_score"]
        roi_delta = roi_metrics["delta_score"]
        regional_delta = regional_metrics["regional_delta"]

        is_scene_novel = scene_delta >= self.scene_novelty_threshold
        is_roi_novel = roi_delta >= self.roi_novelty_threshold
        is_regionally_novel = regional_delta >= self.regional_novelty_threshold

        importance_score = self._clamp01(
            (scene_delta * 0.35)
            + (roi_delta * 0.45)
            + (regional_delta * 0.20)
        )

        result = {
            "scene_delta": scene_delta,
            "roi_delta": roi_delta,
            "regional_delta": regional_delta,

            "scene_changed_ratio": scene_metrics["changed_ratio"],
            "roi_changed_ratio": roi_metrics["changed_ratio"],
            "scene_mean_delta": scene_metrics["mean_delta"],
            "roi_mean_delta": roi_metrics["mean_delta"],

            "is_scene_novel": is_scene_novel,
            "is_roi_novel": is_roi_novel,
            "is_regionally_novel": is_regionally_novel,
            "is_meaningfully_different": (
                is_scene_novel or is_roi_novel or is_regionally_novel
            ),

            "importance_score": importance_score,

            "regional_cells": regional_metrics["cells"],
            "dominant_region": regional_metrics["dominant_region"],

            "has_previous_scene": self.previous_scene is not None,
            "has_previous_roi": self.previous_roi is not None,
        }

        self.previous_scene = scene_gray
        self.previous_roi = roi_gray

        return result

    def _prepare_gray(self, frame):
        if frame is None:
            return None

        if not hasattr(frame, "size") or frame.size == 0:
            return None

        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()

        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        height, width = gray.shape[:2]

        if width <= 0 or height <= 0:
            return None

        scale = self.resize_width / float(width)
        resize_height = max(1, int(height * scale))

        return cv2.resize(
            gray,
            (self.resize_width, resize_height),
            interpolation=cv2.INTER_AREA
        )

    def _delta_metrics(self, previous, current):
        if previous is None or current is None:
            return self._empty_delta()

        if previous.shape != current.shape:
            current = cv2.resize(
                current,
                (previous.shape[1], previous.shape[0]),
                interpolation=cv2.INTER_AREA
            )

        delta = cv2.absdiff(previous, current)

        changed_mask = delta >= self.pixel_change_threshold
        changed_ratio = float(np.count_nonzero(changed_mask)) / float(delta.size)

        mean_delta = float(np.mean(delta)) / 255.0

        delta_score = self._clamp01(
            (changed_ratio * 0.70)
            + (mean_delta * 0.30)
        )

        return {
            "changed_ratio": changed_ratio,
            "mean_delta": mean_delta,
            "delta_score": delta_score
        }

    def _regional_metrics(self, previous, current):
        if previous is None or current is None:
            return {
                "regional_delta": 0.0,
                "cells": [],
                "dominant_region": None
            }

        if previous.shape != current.shape:
            current = cv2.resize(
                current,
                (previous.shape[1], previous.shape[0]),
                interpolation=cv2.INTER_AREA
            )

        height, width = current.shape[:2]

        cell_scores = []

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                y1 = int((row / self.grid_rows) * height)
                y2 = int(((row + 1) / self.grid_rows) * height)
                x1 = int((col / self.grid_cols) * width)
                x2 = int(((col + 1) / self.grid_cols) * width)

                previous_cell = previous[y1:y2, x1:x2]
                current_cell = current[y1:y2, x1:x2]

                metrics = self._delta_metrics(previous_cell, current_cell)

                cell_scores.append({
                    "row": row,
                    "col": col,
                    "score": metrics["delta_score"],
                    "changed_ratio": metrics["changed_ratio"],
                    "mean_delta": metrics["mean_delta"]
                })

        if not cell_scores:
            return {
                "regional_delta": 0.0,
                "cells": [],
                "dominant_region": None
            }

        dominant_cell = max(cell_scores, key=lambda cell: cell["score"])

        average_score = sum(cell["score"] for cell in cell_scores) / len(cell_scores)
        max_score = dominant_cell["score"]

        regional_delta = self._clamp01(
            (average_score * 0.45)
            + (max_score * 0.55)
        )

        return {
            "regional_delta": regional_delta,
            "cells": cell_scores,
            "dominant_region": {
                "row": dominant_cell["row"],
                "col": dominant_cell["col"],
                "score": dominant_cell["score"]
            }
        }

    def _empty_delta(self):
        return {
            "changed_ratio": 0.0,
            "mean_delta": 0.0,
            "delta_score": 0.0
        }

    def _empty_result(self):
        return {
            "scene_delta": 0.0,
            "roi_delta": 0.0,
            "regional_delta": 0.0,

            "scene_changed_ratio": 0.0,
            "roi_changed_ratio": 0.0,
            "scene_mean_delta": 0.0,
            "roi_mean_delta": 0.0,

            "is_scene_novel": False,
            "is_roi_novel": False,
            "is_regionally_novel": False,
            "is_meaningfully_different": False,

            "importance_score": 0.0,

            "regional_cells": [],
            "dominant_region": None,

            "has_previous_scene": False,
            "has_previous_roi": False,
        }

    def _clamp01(self, value):
        return max(0.0, min(1.0, float(value)))
