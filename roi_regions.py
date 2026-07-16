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

