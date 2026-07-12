from __future__ import annotations

from dataclasses import dataclass
import base64
import json
import os
from typing import Any

import cv2
import numpy as np

from .config import BehaviorConfig


@dataclass(frozen=True)
class AnalysisResult:
    rewardable: bool
    best_frame_index: int | None
    reason: str
    justification: str
    subject_present: bool | None = None
    subject_label: str | None = None
    object_present: bool | None = None
    object_label: str | None = None
    action_observed: bool | None = None
    target_zone_visible: bool | None = None


class VisionAnalyzer:
    def analyze_contact_sheet(self, contact_sheet: np.ndarray, behavior: BehaviorConfig) -> AnalysisResult:
        raise NotImplementedError


class OpenAIVisionAnalyzer(VisionAnalyzer):
    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        from openai import OpenAI

        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAIVisionAnalyzer")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def analyze_contact_sheet(self, contact_sheet: np.ndarray, behavior: BehaviorConfig) -> AnalysisResult:
        prompt = build_prompt(behavior)
        image_b64 = encode_jpeg_base64(contact_sheet)
        response = self.client.responses.create(
            model=self.model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                ],
            }],
        )
        return parse_analysis_response(response.output_text, behavior.mode)


class DryRunVisionAnalyzer(VisionAnalyzer):
    def __init__(self, rewardable: bool = False):
        self.rewardable = rewardable

    def analyze_contact_sheet(self, contact_sheet: np.ndarray, behavior: BehaviorConfig) -> AnalysisResult:
        return AnalysisResult(
            rewardable=self.rewardable,
            best_frame_index=None,
            reason="Dry-run analyzer did not call an external model.",
            justification="No external analysis was performed.",
        )


def encode_jpeg_base64(frame: np.ndarray) -> str:
    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        raise ValueError("Could not encode contact sheet")
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def build_prompt(behavior: BehaviorConfig) -> str:
    if behavior.mode == "simple":
        return f"""
You are analyzing a numbered contact sheet of sequential frames.

Desired behavior:
{behavior.reward_description}

Return only valid JSON with exactly these keys:
{{
  "rewardable": true,
  "bestFrameIndex": 1,
  "reason": "short explanation",
  "justification": "specific visual evidence"
}}
""".strip()

    return f"""
You are analyzing a numbered contact sheet of sequential frames.

Configured task:
Determine whether the sequence shows a {behavior.subject_label} {behavior.action_label} {behavior.object_label} into or onto the {behavior.target_zone_label}.

A rewardable event requires visible evidence for subject, object, target zone, action, and subject participation.

Return only valid JSON with exactly these keys:
{{
  "subjectPresent": true,
  "subjectLabel": "string or null",
  "objectPresent": true,
  "objectLabel": "string or null",
  "actionObserved": true,
  "targetZoneVisible": true,
  "rewardable": true,
  "bestFrameIndex": 1,
  "reason": "short explanation",
  "justification": "specific visual evidence"
}}
""".strip()


def parse_analysis_response(text: str | None, mode: str) -> AnalysisResult:
    if not text:
        return AnalysisResult(False, None, "No model response.", "")
    data = _loads_model_json(text)
    rewardable = bool(data.get("rewardable", False))
    best_frame = data.get("bestFrameIndex")
    if best_frame is not None and not isinstance(best_frame, int):
        best_frame = None
    result = AnalysisResult(
        rewardable=rewardable,
        best_frame_index=best_frame,
        reason=str(data.get("reason", "")),
        justification=str(data.get("justification", "")),
    )
    if mode == "simple":
        return result
    return AnalysisResult(
        rewardable=result.rewardable,
        best_frame_index=result.best_frame_index,
        reason=result.reason,
        justification=result.justification,
        subject_present=_optional_bool(data.get("subjectPresent")),
        subject_label=_optional_text(data.get("subjectLabel")),
        object_present=_optional_bool(data.get("objectPresent")),
        object_label=_optional_text(data.get("objectLabel")),
        action_observed=_optional_bool(data.get("actionObserved")),
        target_zone_visible=_optional_bool(data.get("targetZoneVisible")),
    )


def _loads_model_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")
    return value


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
