from dataclasses import dataclass
from typing import Optional, Tuple


class ResizeHandle:
    NONE = "none"
    MOVE = "move"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


@dataclass
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        return self.x

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def top(self) -> int:
        return self.y

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


def detect_resize_handle(
    point_x: int,
    point_y: int,
    rect: Rect,
    edge_margin: int = 8,
) -> str:
    near_left = abs(point_x - rect.left) <= edge_margin
    near_right = abs(point_x - rect.right) <= edge_margin
    near_top = abs(point_y - rect.top) <= edge_margin
    near_bottom = abs(point_y - rect.bottom) <= edge_margin

    inside_x = rect.left <= point_x <= rect.right
    inside_y = rect.top <= point_y <= rect.bottom

    if near_left and near_top:
        return ResizeHandle.TOP_LEFT

    if near_right and near_top:
        return ResizeHandle.TOP_RIGHT

    if near_left and near_bottom:
        return ResizeHandle.BOTTOM_LEFT

    if near_right and near_bottom:
        return ResizeHandle.BOTTOM_RIGHT

    if near_left and inside_y:
        return ResizeHandle.LEFT

    if near_right and inside_y:
        return ResizeHandle.RIGHT

    if near_top and inside_x:
        return ResizeHandle.TOP

    if near_bottom and inside_x:
        return ResizeHandle.BOTTOM

    if inside_x and inside_y:
        return ResizeHandle.MOVE

    return ResizeHandle.NONE


def resize_rect_from_drag(
    original: Rect,
    handle: str,
    delta_x: int,
    delta_y: int,
    min_width: int = 10,
    min_height: int = 10,
    bounds: Optional[Rect] = None,
) -> Rect:
    x = original.x
    y = original.y
    width = original.width
    height = original.height

    if handle == ResizeHandle.MOVE:
        x += delta_x
        y += delta_y

    if handle in {ResizeHandle.LEFT, ResizeHandle.TOP_LEFT, ResizeHandle.BOTTOM_LEFT}:
        x += delta_x
        width -= delta_x

    if handle in {ResizeHandle.RIGHT, ResizeHandle.TOP_RIGHT, ResizeHandle.BOTTOM_RIGHT}:
        width += delta_x

    if handle in {ResizeHandle.TOP, ResizeHandle.TOP_LEFT, ResizeHandle.TOP_RIGHT}:
        y += delta_y
        height -= delta_y

    if handle in {ResizeHandle.BOTTOM, ResizeHandle.BOTTOM_LEFT, ResizeHandle.BOTTOM_RIGHT}:
        height += delta_y

    if width < min_width:
        if handle in {ResizeHandle.LEFT, ResizeHandle.TOP_LEFT, ResizeHandle.BOTTOM_LEFT}:
            x -= min_width - width
        width = min_width

    if height < min_height:
        if handle in {ResizeHandle.TOP, ResizeHandle.TOP_LEFT, ResizeHandle.TOP_RIGHT}:
            y -= min_height - height
        height = min_height

    resized = Rect(int(x), int(y), int(width), int(height))

    if bounds is not None:
        resized = clamp_rect_to_bounds(resized, bounds)

    return resized


def clamp_rect_to_bounds(rect: Rect, bounds: Rect) -> Rect:
    width = min(rect.width, bounds.width)
    height = min(rect.height, bounds.height)

    x = max(bounds.left, min(rect.x, bounds.right - width))
    y = max(bounds.top, min(rect.y, bounds.bottom - height))

    return Rect(
        x=int(x),
        y=int(y),
        width=int(width),
        height=int(height),
    )

