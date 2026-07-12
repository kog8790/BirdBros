from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import json


class ConfigError(ValueError):
    pass


ActionKind = Literal["status", "mouse_click", "keyboard_shortcut", "webhook", "shell_command"]
InputKind = Literal["screen_capture", "video_file"]
ModeKind = Literal["simple", "advanced"]


@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str) -> "Region":
        left = _int(data, "left", name, minimum=0)
        top = _int(data, "top", name, minimum=0)
        width = _int(data, "width", name, minimum=1, maximum=10000)
        height = _int(data, "height", name, minimum=1, maximum=10000)
        return cls(left=left, top=top, width=width, height=height)

    def as_mss(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "width": self.width, "height": self.height}


@dataclass(frozen=True)
class Roi:
    x_pct: float
    y_pct: float
    w_pct: float
    h_pct: float

    @classmethod
    def from_dict(cls, data: dict[str, Any], name: str) -> "Roi":
        x = _float(data, "x_pct", name, minimum=0.0, maximum=1.0)
        y = _float(data, "y_pct", name, minimum=0.0, maximum=1.0)
        w = _float(data, "w_pct", name, minimum=0.001, maximum=1.0)
        h = _float(data, "h_pct", name, minimum=0.001, maximum=1.0)
        if x + w > 1.0:
            raise ConfigError(f"{name}.x_pct + {name}.w_pct must be <= 1.0")
        if y + h > 1.0:
            raise ConfigError(f"{name}.y_pct + {name}.h_pct must be <= 1.0")
        return cls(x_pct=x, y_pct=y, w_pct=w, h_pct=h)

    def to_pixels(self, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
        x = int(self.x_pct * frame_width)
        y = int(self.y_pct * frame_height)
        w = max(1, int(self.w_pct * frame_width))
        h = max(1, int(self.h_pct * frame_height))
        return x, y, min(w, frame_width - x), min(h, frame_height - y)


@dataclass(frozen=True)
class InputConfig:
    kind: InputKind = "screen_capture"
    screen_region: Region = field(default_factory=lambda: Region(100, 100, 900, 700))
    video_path: str = ""
    loop_video: bool = True
    fps: int = 6

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InputConfig":
        kind = _choice(data, "kind", "input", {"screen_capture", "video_file"}, default="screen_capture")
        region = Region.from_dict(_dict(data, "screen_region", "input", default={}), "input.screen_region")
        fps = _int(data, "fps", "input", minimum=1, maximum=120, default=6)
        video_path = str(data.get("video_path", ""))
        if kind == "video_file" and not video_path:
            raise ConfigError("input.video_path is required when input.kind is video_file")
        return cls(
            kind=kind,
            screen_region=region,
            video_path=video_path,
            loop_video=bool(data.get("loop_video", True)),
            fps=fps,
        )


@dataclass(frozen=True)
class BehaviorConfig:
    mode: ModeKind = "simple"
    reward_description: str = "A bird drops litter into a receptacle."
    subject_label: str = "non-human animal"
    object_label: str = "man-made litter or trash"
    target_zone_label: str = "trash receptacle"
    action_label: str = "depositing"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BehaviorConfig":
        mode = _choice(data, "mode", "behavior", {"simple", "advanced"}, default="simple")
        return cls(
            mode=mode,
            reward_description=_non_empty_text(data, "reward_description", "behavior", default=cls.reward_description),
            subject_label=_non_empty_text(data, "subject_label", "behavior", default=cls.subject_label),
            object_label=_non_empty_text(data, "object_label", "behavior", default=cls.object_label),
            target_zone_label=_non_empty_text(data, "target_zone_label", "behavior", default=cls.target_zone_label),
            action_label=_non_empty_text(data, "action_label", "behavior", default=cls.action_label),
        )


@dataclass(frozen=True)
class MotionConfig:
    min_area: int = 5000
    warmup_seconds: float = 3.0
    still_frames_to_end: int = 4
    pre_event_frames: int = 12
    max_event_frames: int = 60

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MotionConfig":
        return cls(
            min_area=_int(data, "min_area", "motion", minimum=1, maximum=500000, default=5000),
            warmup_seconds=_float(data, "warmup_seconds", "motion", minimum=0.0, maximum=60.0, default=3.0),
            still_frames_to_end=_int(data, "still_frames_to_end", "motion", minimum=1, maximum=120, default=4),
            pre_event_frames=_int(data, "pre_event_frames", "motion", minimum=0, maximum=120, default=12),
            max_event_frames=_int(data, "max_event_frames", "motion", minimum=3, maximum=300, default=60),
        )


@dataclass(frozen=True)
class PrivacyConfig:
    save_diagnostics: bool = False
    diagnostics_dir: str = "diagnostics"
    retention_days: int = 7

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrivacyConfig":
        return cls(
            save_diagnostics=bool(data.get("save_diagnostics", False)),
            diagnostics_dir=str(data.get("diagnostics_dir", "diagnostics")),
            retention_days=_int(data, "retention_days", "privacy", minimum=1, maximum=365, default=7),
        )


@dataclass(frozen=True)
class RewardAction:
    kind: ActionKind = "status"
    click_sequence: tuple[dict[str, float], ...] = ()
    keys: tuple[str, ...] = ()
    url: str = ""
    method: Literal["POST", "GET"] = "POST"
    timeout: float = 5.0
    headers: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    bearer_token_env: str = ""
    command: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any], developer_mode: bool) -> "RewardAction":
        kind = _choice(
            data,
            "kind",
            "reward_action",
            {"status", "mouse_click", "keyboard_shortcut", "webhook", "shell_command"},
            default="status",
        )
        if kind == "shell_command" and not developer_mode:
            raise ConfigError("reward_action.shell_command requires developer_mode=true")
        method = _choice(data, "method", "reward_action", {"POST", "GET"}, default="POST")
        command = data.get("command", [])
        if isinstance(command, str):
            raise ConfigError("reward_action.command must be an argv list, not a shell string")
        if command and not all(isinstance(item, str) and item for item in command):
            raise ConfigError("reward_action.command must contain non-empty strings")
        headers = data.get("headers", {})
        payload = data.get("payload", {})
        if not isinstance(headers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in headers.items()):
            raise ConfigError("reward_action.headers must be an object of string values")
        if not isinstance(payload, dict):
            raise ConfigError("reward_action.payload must be an object")
        return cls(
            kind=kind,
            click_sequence=tuple(_parse_click_sequence(data.get("click_sequence", []))),
            keys=tuple(_parse_keys(data.get("keys", []))),
            url=str(data.get("url", "")),
            method=method,
            timeout=_float(data, "timeout", "reward_action", minimum=0.1, maximum=60.0, default=5.0),
            headers=dict(headers),
            payload=dict(payload),
            bearer_token_env=str(data.get("bearer_token_env", "")),
            command=tuple(command),
        )


@dataclass(frozen=True)
class AppConfig:
    input: InputConfig
    subject_roi: Roi
    object_roi: Roi
    behavior: BehaviorConfig
    motion: MotionConfig
    privacy: PrivacyConfig
    reward_action: RewardAction
    no_reward_action: RewardAction
    developer_mode: bool = False
    openai_model: str = "gpt-4o"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        if not isinstance(data, dict):
            raise ConfigError("config root must be an object")
        developer_mode = bool(data.get("developer_mode", False))
        return cls(
            input=InputConfig.from_dict(_dict(data, "input", "config", default={})),
            subject_roi=Roi.from_dict(_dict(data, "subject_roi", "config", default={}), "subject_roi"),
            object_roi=Roi.from_dict(_dict(data, "object_roi", "config", default={}), "object_roi"),
            behavior=BehaviorConfig.from_dict(_dict(data, "behavior", "config", default={})),
            motion=MotionConfig.from_dict(_dict(data, "motion", "config", default={})),
            privacy=PrivacyConfig.from_dict(_dict(data, "privacy", "config", default={})),
            reward_action=RewardAction.from_dict(_dict(data, "reward_action", "config", default={}), developer_mode),
            no_reward_action=RewardAction.from_dict(_dict(data, "no_reward_action", "config", default={"kind": "status"}), developer_mode),
            developer_mode=developer_mode,
            openai_model=_non_empty_text(data, "openai_model", "config", default="gpt-4o"),
        )


def load_config(path: str | Path) -> AppConfig:
    with open(path, "r", encoding="utf-8") as file:
        return AppConfig.from_dict(json.load(file))


def _dict(data: dict[str, Any], key: str, scope: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    value = data.get(key, default)
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ConfigError(f"{scope}.{key} must be an object")
    return value


def _int(data: dict[str, Any], key: str, scope: str, minimum: int, maximum: int | None = None, default: int | None = None) -> int:
    value = data.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{scope}.{key} must be an integer")
    if value < minimum:
        raise ConfigError(f"{scope}.{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{scope}.{key} must be <= {maximum}")
    return value


def _float(data: dict[str, Any], key: str, scope: str, minimum: float, maximum: float | None = None, default: float | None = None) -> float:
    value = data.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{scope}.{key} must be numeric")
    value = float(value)
    if value < minimum:
        raise ConfigError(f"{scope}.{key} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{scope}.{key} must be <= {maximum}")
    return value


def _choice(data: dict[str, Any], key: str, scope: str, choices: set[str], default: str) -> Any:
    value = data.get(key, default)
    if value not in choices:
        raise ConfigError(f"{scope}.{key} must be one of: {', '.join(sorted(choices))}")
    return value


def _non_empty_text(data: dict[str, Any], key: str, scope: str, default: str) -> str:
    value = str(data.get(key, default)).strip()
    if not value:
        raise ConfigError(f"{scope}.{key} cannot be blank")
    if len(value) > 1000:
        raise ConfigError(f"{scope}.{key} is too long")
    return value


def _parse_keys(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError("reward_action.keys must be a list")
    keys = [str(item).strip().lower() for item in value]
    if any(not item for item in keys):
        raise ConfigError("reward_action.keys cannot contain blank values")
    return keys


def _parse_click_sequence(value: Any) -> list[dict[str, float]]:
    if not isinstance(value, list):
        raise ConfigError("reward_action.click_sequence must be a list")
    steps: list[dict[str, float]] = []
    for index, step in enumerate(value, start=1):
        if not isinstance(step, dict):
            raise ConfigError(f"reward_action.click_sequence[{index}] must be an object")
        steps.append({
            "x": _float(step, "x", f"reward_action.click_sequence[{index}]", minimum=0, maximum=10000),
            "y": _float(step, "y", f"reward_action.click_sequence[{index}]", minimum=0, maximum=10000),
            "hold_duration": _float(step, "hold_duration", f"reward_action.click_sequence[{index}]", minimum=0, maximum=10, default=0.0),
            "delay_after": _float(step, "delay_after", f"reward_action.click_sequence[{index}]", minimum=0, maximum=60, default=0.1),
            "move_duration": _float(step, "move_duration", f"reward_action.click_sequence[{index}]", minimum=0, maximum=10, default=0.0),
        })
    return steps
