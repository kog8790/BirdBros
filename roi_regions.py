from dataclasses import dataclass, field
from typing import Iterable, Set, Tuple

from capture_regions import CaptureRegion


@dataclass
class ROI:
    key: str
    label: str
    x: int
    y: int
    width: int
    height: int
    roles: Set[str] = field(default_factory=set)

    min_width: int = 10
    min_height: int = 10
    is_visible: bool = True
    is_editable: bool = True

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def is_trigger(self) -> bool:
        return "trigger" in self.roles

    @property
    def is_subject(self) -> bool:
        return "subject" in self.roles

    @property
    def is_object(self) -> bool:
        return "object" in self.roles

    @property
    def is_exclusion(self) -> bool:
        return "exclusion" in self.roles

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def add_role(self, role: str) -> None:
        self.roles.add(role)

    def remove_role(self, role: str) -> None:
        self.roles.discard(role)

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def clamp_to_capture(self, capture_region: CaptureRegion) -> None:
        self.width = max(self.min_width, int(self.width))
        self.height = max(self.min_height, int(self.height))

        max_x = max(0, capture_region.width - self.width)
        max_y = max(0, capture_region.height - self.height)

        self.x = max(0, min(int(self.x), max_x))
        self.y = max(0, min(int(self.y), max_y))

        self.width = min(self.width, capture_region.width - self.x)
        self.height = min(self.height, capture_region.height - self.y)

    def to_screen_tuple(self, capture_region: CaptureRegion) -> Tuple[int, int, int, int]:
        screen_x, screen_y = capture_region.local_to_screen(self.x, self.y)

        return (
            int(screen_x),
            int(screen_y),
            int(self.width),
            int(self.height),
        )

    @classmethod
    def from_config(
        cls,
        key: str,
        label: str,
        config: dict,
        roles: Iterable[str] = (),
    ) -> "ROI":
        region = config.get(key, {})

        return cls(
            key=key,
            label=label,
            x=int(region.get("x", 0)),
            y=int(region.get("y", 0)),
            width=int(region.get("w", region.get("width", 100))),
            height=int(region.get("h", region.get("height", 100))),
            roles=set(roles),
        )

    def to_config(self) -> dict:
        return {
            "x": int(self.x),
            "y": int(self.y),
            "w": int(self.width),
            "h": int(self.height),
        }

    @classmethod
    def from_percent_config(
        cls,
        key: str,
        label: str,
        config: dict,
        capture_region: CaptureRegion,
        roles: Iterable[str] = (),
    ) -> "ROI":
        region = config.get(key, {})

        roi = cls(
            key=key,
            label=label,
            x=int(float(region.get("x_pct", 0.0)) * capture_region.width),
            y=int(float(region.get("y_pct", 0.0)) * capture_region.height),
            width=int(float(region.get("w_pct", 0.0)) * capture_region.width),
            height=int(float(region.get("h_pct", 0.0)) * capture_region.height),
            roles=set(roles),
        )

        roi.clamp_to_capture(capture_region)
        return roi

    def to_percent_config(self, capture_region: CaptureRegion) -> dict:
        capture_width = max(1, int(capture_region.width))
        capture_height = max(1, int(capture_region.height))

        self.clamp_to_capture(capture_region)

        return {
            "x_pct": float(self.x) / capture_width,
            "y_pct": float(self.y) / capture_height,
            "w_pct": float(self.width) / capture_width,
            "h_pct": float(self.height) / capture_height,
        }

    @classmethod
    def subject(
        cls,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> "ROI":
        return cls(
            key="subject_roi",
            label="Subject ROI",
            x=int(x),
            y=int(y),
            width=max(1, int(width)),
            height=max(1, int(height)),
            roles={"subject"},
        )

    @classmethod
    def trigger_object(
        cls,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> "ROI":
        return cls(
            key="object_roi",
            label="Trigger ROI",
            x=int(x),
            y=int(y),
            width=max(1, int(width)),
            height=max(1, int(height)),
            roles={"trigger", "object"},
        )

    @classmethod
    def from_screen_tuple_relative_to_capture(
        cls,
        key: str,
        label: str,
        rect_tuple,
        capture_region: CaptureRegion,
        roles: Iterable[str] = (),
    ) -> "ROI":
        screen_x, screen_y, width, height = rect_tuple
        local_x, local_y = capture_region.screen_to_local(screen_x, screen_y)

        roi = cls(
            key=key,
            label=label,
            x=int(local_x),
            y=int(local_y),
            width=max(1, int(width)),
            height=max(1, int(height)),
            roles=set(roles),
        )
        roi.clamp_to_capture(capture_region)

        return roi

    @classmethod
    def trigger_object_from_screen_tuple(
        cls,
        rect_tuple,
        capture_region: CaptureRegion,
    ) -> "ROI":
        return cls.from_screen_tuple_relative_to_capture(
            key="object_roi",
            label="Trigger ROI",
            rect_tuple=rect_tuple,
            capture_region=capture_region,
            roles={"trigger", "object"},
        )

    @classmethod
    def subject_from_percent_config(
        cls,
        config: dict,
        capture_region: CaptureRegion,
    ) -> "ROI":
        return cls.from_percent_config(
            key="subject_roi",
            label="Subject ROI",
            config=config,
            capture_region=capture_region,
            roles={"subject"},
        )

    @classmethod
    def trigger_object_from_percent_config(
        cls,
        config: dict,
        capture_region: CaptureRegion,
    ) -> "ROI":
        return cls.from_percent_config(
            key="object_roi",
            label="Trigger ROI",
            config=config,
            capture_region=capture_region,
            roles={"trigger", "object"},
        )


class ROICollection:
    def __init__(self, rois=None):
        self.rois = list(rois or [])

    def add(self, roi: ROI) -> None:
        self.rois.append(roi)

    def by_role(self, role: str):
        return [roi for roi in self.rois if roi.has_role(role)]

    def by_key(self, key: str):
        return [roi for roi in self.rois if roi.key == key]

    def editable(self):
        return [roi for roi in self.rois if roi.is_editable]

    def visible(self):
        return [roi for roi in self.rois if roi.is_visible]

