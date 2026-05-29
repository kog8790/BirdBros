""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Handles OpenAI Vision API calls for Bird Bros image/event analysis.

DESIGN INTENT:
Keep API communication and prompt construction isolated so the rest of the
system remains model-agnostic and open-source configurable.
"""

import base64
import json
from openai import OpenAI

from image_subject import image_subject
from image_object import image_object


class vision_api:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        if not api_key:
            raise ValueError("vision_api requires a valid api_key")

        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def _encode_image(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")

    def _clean_json_text(self, text: str) -> str:
        if not text:
            return ""

        cleaned = text.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):].strip()

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        return cleaned

    def _send_request(self, prompt: str, image_b64: str) -> str | None:
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image_url": f"data:image/jpeg;base64,{image_b64}"
                            }
                        ]
                    }
                ]
            )

            return response.output_text

        except Exception as e:
            print(f"[vision_api] API error: {e}")
            return None

    # ================================
    # CONFIGURABLE CONTACT SHEET PROMPT
    # ================================

    def build_event_contact_sheet_prompt(
        self,
        subject_label: str = "non-human animal",
        object_label: str = "man-made litter or trash",
        target_zone_label: str = "trash receptacle",
        action_label: str = "depositing"
    ) -> str:
        return f"""
You are analyzing a numbered contact sheet of sequential frames from an automated training system.

FRAME ORDER:
- Frames are ordered in time.
- Read them left-to-right, top-to-bottom.
- Frame 1 is earliest.
- The highest-numbered frame is latest.

CONFIGURED TASK:
Determine whether the sequence shows a {subject_label} {action_label} {object_label} into or onto the {target_zone_label}.

IMPORTANT:
Base your judgment on the sequence as a whole, not a single frame.

A rewardable event requires ALL of the following:
1. A {subject_label} is visibly involved in the event.
2. A {object_label} is visible or becomes visible during the sequence.
3. The {object_label} appears to move into, land in, or be placed into/onto the {target_zone_label}.
4. The sequence supports that the {subject_label} caused or participated in the action.

Do NOT mark rewardable if:
- The {subject_label} is absent.
- The {object_label} is absent.
- The {object_label} is already present with no clear action occurring.
- The object is unrelated to the configured object type.
- The action is ambiguous or uncertain.
- The {target_zone_label} itself is mistaken for the object.

Return ONLY valid JSON with these exact keys:
{{
  "subjectPresent": true/false,
  "subjectLabel": "string or null",
  "objectPresent": true/false,
  "objectLabel": "string or null",
  "actionObserved": true/false,
  "targetZoneVisible": true/false,
  "rewardable": true/false,
  "bestFrameIndex": integer or null,
  "reason": "short explanation",
  "justification": "specific visual evidence supporting the decision"
}}
""".strip()

    def analyze_event_contact_sheet(
        self,
        image_bytes: bytes,
        subject_label: str = "non-human animal",
        object_label: str = "man-made litter or trash",
        target_zone_label: str = "trash receptacle",
        action_label: str = "depositing"
    ) -> dict:
        prompt = self.build_event_contact_sheet_prompt(
            subject_label=subject_label,
            object_label=object_label,
            target_zone_label=target_zone_label,
            action_label=action_label
        )

        image_b64 = self._encode_image(image_bytes)
        response = self._send_request(prompt, image_b64)

        default_result = {
            "subjectPresent": False,
            "subjectLabel": None,
            "objectPresent": False,
            "objectLabel": None,
            "actionObserved": False,
            "targetZoneVisible": False,
            "rewardable": False,
            "bestFrameIndex": None,
            "reason": "No valid API response",
            "justification": ""
        }

        if not response:
            return default_result

        try:
            cleaned = self._clean_json_text(response)
            data = json.loads(cleaned)

            return {
                "subjectPresent": bool(data.get("subjectPresent", False)),
                "subjectLabel": data.get("subjectLabel"),
                "objectPresent": bool(data.get("objectPresent", False)),
                "objectLabel": data.get("objectLabel"),
                "actionObserved": bool(data.get("actionObserved", False)),
                "targetZoneVisible": bool(data.get("targetZoneVisible", False)),
                "rewardable": bool(data.get("rewardable", False)),
                "bestFrameIndex": data.get("bestFrameIndex"),
                "reason": data.get("reason") or "",
                "justification": data.get("justification") or ""
            }

        except Exception as e:
            print(f"[vision_api] Contact sheet parse error: {e}\nResponse was: {response}")
            default_result["reason"] = f"Failed to parse API response: {e}"
            return default_result

    # ================================
    # LEGACY SUBJECT ANALYSIS
    # ================================

    def analyze_subject(self, image_bytes: bytes) -> image_subject:
        prompt = (
            "You are an expert in animal behavior and environmental cleanup. "
            "Examine this image and answer the following. "
            "Respond ONLY with valid JSON.\n\n"
            "Required keys:\n"
            "- liveLabel: string or null\n"
            "- hodlBool: boolean\n"
            "- hodlClass: string or null\n"
            "- isMatch: boolean\n\n"
            "Questions:\n"
            "1. Is a non-human animal the primary subject? If yes, what kind? -> liveLabel\n"
            "2. Is the animal holding anything? -> hodlBool\n"
            "3. If yes, what is the object? -> hodlClass\n"
            "4. Would that object be considered trash? -> isMatch"
        )

        image_b64 = self._encode_image(image_bytes)
        response = self._send_request(prompt, image_b64)

        if not response:
            return image_subject(None, False, None, False)

        try:
            cleaned = self._clean_json_text(response)
            data = json.loads(cleaned)

            return image_subject(
                liveLabel=data.get("liveLabel"),
                hodlBool=bool(data.get("hodlBool", False)),
                hodlClass=data.get("hodlClass"),
                isMatch=bool(data.get("isMatch", False))
            )

        except Exception as e:
            print(f"[vision_api] Subject parse error: {e}\nResponse was: {response}")
            return image_subject(None, False, None, False)

    # ================================
    # LEGACY OBJECT VALIDATION
    # ================================

    def analyze_object(self, image_bytes: bytes, expected_label: str) -> image_object:
        prompt = (
            f"You previously saw a bird holding '{expected_label}'. "
            "Now examine this dropped item image.\n\n"
            "Respond ONLY with valid JSON.\n\n"
            "Required keys:\n"
            "- objectLabel: string or null\n"
            "- isMatch: boolean\n\n"
            "Questions:\n"
            "1. Is this the same object you saw before? -> isMatch\n"
            "2. If true, echo back the same label. If false, identify the object. -> objectLabel"
        )

        image_b64 = self._encode_image(image_bytes)
        response = self._send_request(prompt, image_b64)

        if not response:
            return image_object(None, False)

        try:
            cleaned = self._clean_json_text(response)
            data = json.loads(cleaned)

            return image_object(
                objectLabel=data.get("objectLabel"),
                isMatch=bool(data.get("isMatch", False))
            )

        except Exception as e:
            print(f"[vision_api] Object parse error: {e}\nResponse was: {response}")
            return image_object(None, False)

    # ================================
    # GENERAL API HELPERS
    # ================================

    def describe_image(self, image_bytes: bytes) -> str | None:
        prompt = "Describe this image in one detailed English sentence."
        image_b64 = self._encode_image(image_bytes)
        return self._send_request(prompt, image_b64)

    def custom_query(self, image_bytes: bytes, custom_prompt: str) -> str | None:
        image_b64 = self._encode_image(image_bytes)
        return self._send_request(custom_prompt, image_b64)


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:

main.py/contact_sheet_builder
    ↓
vision_api.analyze_event_contact_sheet()
    ↓
OpenAI returns structured event interpretation
    ↓
main.py triggers reward/no reward

DESIGN INTENT:
The event prompt is configurable through subject/object/action/target-zone labels
so open-source users can adapt the system beyond birds and litter.
"""
