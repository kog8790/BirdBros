from dataclasses import dataclass
from typing import Tuple


@dataclass
class CaptureRegion:
    left: int
    top: int
    width: int
    height: int

    min_width: int = 20
    min_height: int = 20

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

    def clamp_size(self) -> None:
        self.width = max(self.min_width, int(self.width))
        self.height = max(self.min_height, int(self.height))

    def contains_screen_point(self, x: int, y: int) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def screen_to_local(self, x: int, y: int) -> Tuple[int, int]:
        return (int(x - self.left), int(y - self.top))

    def local_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        return (int(self.left + x), int(self.top + y))

    def interaction_padding_px(
        self,
        ratio: float = 0.02,
        min_px: int = 8,
        max_px: int = 28,
    ) -> int:
        """
        Derive invisible interaction padding from Capture Region size.

        The percentage is the source of truth; min/max are guardrails so tiny
        regions remain usable and very large regions do not create an overly
        grabby invisible border.
        """

        base_dimension = max(1, min(int(self.width), int(self.height)))
        derived_padding = int(round(base_dimension * ratio))

        return max(int(min_px), min(int(derived_padding), int(max_px)))

    def expanded_for_interaction(
        self,
        ratio: float = 0.02,
        min_px: int = 8,
        max_px: int = 28,
    ) -> "CaptureRegion":
        padding = self.interaction_padding_px(
            ratio=ratio,
            min_px=min_px,
            max_px=max_px,
        )

        return CaptureRegion(
            left=int(self.left - padding),
            top=int(self.top - padding),
            width=int(self.width + padding * 2),
            height=int(self.height + padding * 2),
            min_width=self.min_width,
            min_height=self.min_height,
        )

    @classmethod
    def from_config(cls, config: dict) -> "CaptureRegion":
        region = config.get("capture_region", {})

        return cls(
            left=int(region.get("left", 0)),
            top=int(region.get("top", 0)),
            width=int(region.get("width", 640)),
            height=int(region.get("height", 480)),
        )

    def to_config(self) -> dict:
        self.clamp_size()

        return {
            "left": int(self.left),
            "top": int(self.top),
            "width": int(self.width),
            "height": int(self.height),
        }

    @classmethod
    def from_screen_tuple(cls, rect_tuple) -> "CaptureRegion":
        x, y, width, height = rect_tuple

        region = cls(
            left=max(0, int(x)),
            top=max(0, int(y)),
            width=max(1, int(width)),
            height=max(1, int(height)),
        )
        region.clamp_size()

        return region


class CaptureRegionCollection:
    def __init__(self, regions=None):
        self.regions = list(regions or [])

    def add(self, region: CaptureRegion) -> None:
        self.regions.append(region)

    def primary(self):
        return self.regions[0] if self.regions else None

    def all(self):
        return list(self.regions)

    def __iter__(self):
        return iter(self.regions)

    def __len__(self):
        return len(self.regions)

    def __getitem__(self, index):
        return self.regions[index]


