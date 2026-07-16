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


RESIZE_HANDLES = {
    ResizeHandle.LEFT,
    ResizeHandle.RIGHT,
    ResizeHandle.TOP,
    ResizeHandle.BOTTOM,
    ResizeHandle.TOP_LEFT,
    ResizeHandle.TOP_RIGHT,
    ResizeHandle.BOTTOM_LEFT,
    ResizeHandle.BOTTOM_RIGHT,
}


CORNER_HANDLES = {
    ResizeHandle.TOP_LEFT,
    ResizeHandle.TOP_RIGHT,
    ResizeHandle.BOTTOM_LEFT,
    ResizeHandle.BOTTOM_RIGHT,
}


EDGE_HANDLES = {
    ResizeHandle.LEFT,
    ResizeHandle.RIGHT,
    ResizeHandle.TOP,
    ResizeHandle.BOTTOM,
}


VALID_HANDLES = {
    ResizeHandle.NONE,
    ResizeHandle.MOVE,
    *RESIZE_HANDLES,
}


HORIZONTAL_RESIZE_HANDLES = {
    ResizeHandle.LEFT,
    ResizeHandle.RIGHT,
}


VERTICAL_RESIZE_HANDLES = {
    ResizeHandle.TOP,
    ResizeHandle.BOTTOM,
}


DIAGONAL_RESIZE_HANDLES_FORWARD = {
    ResizeHandle.TOP_RIGHT,
    ResizeHandle.BOTTOM_LEFT,
}


DIAGONAL_RESIZE_HANDLES_BACKWARD = {
    ResizeHandle.TOP_LEFT,
    ResizeHandle.BOTTOM_RIGHT,
}


@dataclass(frozen=True)
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

    @property
    def center_x(self) -> int:
        return self.x + self.width // 2

    @property
    def center_y(self) -> int:
        return self.y + self.height // 2

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def normalized(self) -> "Rect":
        x = self.x
        y = self.y
        width = self.width
        height = self.height

        if width < 0:
            x = self.x + width
            width = abs(width)

        if height < 0:
            y = self.y + height
            height = abs(height)

        return Rect(
            x=int(x),
            y=int(y),
            width=int(width),
            height=int(height),
        )

    def contains_point(self, point_x: int, point_y: int) -> bool:
        normalized = self.normalized()

        return (
            normalized.left <= point_x <= normalized.right
            and normalized.top <= point_y <= normalized.bottom
        )

    def inflated(self, amount: int) -> "Rect":
        return Rect(
            x=self.x - amount,
            y=self.y - amount,
            width=self.width + amount * 2,
            height=self.height + amount * 2,
        ).normalized()

    def translated(self, delta_x: int, delta_y: int) -> "Rect":
        return Rect(
            x=self.x + delta_x,
            y=self.y + delta_y,
            width=self.width,
            height=self.height,
        )

    @classmethod
    def from_tuple(cls, rect_tuple: Tuple[int, int, int, int]) -> "Rect":
        x, y, width, height = rect_tuple

        return cls(
            x=int(x),
            y=int(y),
            width=int(width),
            height=int(height),
        )


def is_resize_handle(handle: str) -> bool:
    return handle in RESIZE_HANDLES


def is_corner_handle(handle: str) -> bool:
    return handle in CORNER_HANDLES


def is_edge_handle(handle: str) -> bool:
    return handle in EDGE_HANDLES


def normalize_handle(handle: Optional[str]) -> str:
    if handle in VALID_HANDLES:
        return handle

    return ResizeHandle.NONE


def cursor_role_for_handle(handle: str) -> str:
    """
    Return a Qt-agnostic cursor role for the given handle.

    overlay_window.py can map these roles to Qt cursors later:
    - default
    - move
    - resize_horizontal
    - resize_vertical
    - resize_diagonal_forward
    - resize_diagonal_backward
    """

    handle = normalize_handle(handle)

    if handle == ResizeHandle.MOVE:
        return "move"

    if handle in HORIZONTAL_RESIZE_HANDLES:
        return "resize_horizontal"

    if handle in VERTICAL_RESIZE_HANDLES:
        return "resize_vertical"

    if handle in DIAGONAL_RESIZE_HANDLES_FORWARD:
        return "resize_diagonal_forward"

    if handle in DIAGONAL_RESIZE_HANDLES_BACKWARD:
        return "resize_diagonal_backward"

    return "default"


def detect_resize_handle(
    point_x: int,
    point_y: int,
    rect: Rect,
    edge_margin: int = 8,
    *,
    include_move: bool = True,
) -> str:
    """
    Detect which part of a rectangle a point is interacting with.

    The resize hit area is intentionally allowed to extend slightly outside
    the rectangle by edge_margin. Move detection only applies inside the
    actual rectangle.
    """

    rect = rect.normalized()
    outer_rect = rect.inflated(edge_margin)

    if not outer_rect.contains_point(point_x, point_y):
        return ResizeHandle.NONE

    near_left = abs(point_x - rect.left) <= edge_margin
    near_right = abs(point_x - rect.right) <= edge_margin
    near_top = abs(point_y - rect.top) <= edge_margin
    near_bottom = abs(point_y - rect.bottom) <= edge_margin

    within_vertical_band = (
        rect.top - edge_margin <= point_y <= rect.bottom + edge_margin
    )
    within_horizontal_band = (
        rect.left - edge_margin <= point_x <= rect.right + edge_margin
    )

    if near_left and near_top:
        return ResizeHandle.TOP_LEFT

    if near_right and near_top:
        return ResizeHandle.TOP_RIGHT

    if near_left and near_bottom:
        return ResizeHandle.BOTTOM_LEFT

    if near_right and near_bottom:
        return ResizeHandle.BOTTOM_RIGHT

    if near_left and within_vertical_band:
        return ResizeHandle.LEFT

    if near_right and within_vertical_band:
        return ResizeHandle.RIGHT

    if near_top and within_horizontal_band:
        return ResizeHandle.TOP

    if near_bottom and within_horizontal_band:
        return ResizeHandle.BOTTOM

    if include_move and rect.contains_point(point_x, point_y):
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
    """
    Return a new rectangle after applying a drag delta to a resize/move handle.
    """

    original = original.normalized()
    handle = normalize_handle(handle)

    min_width = max(1, int(min_width))
    min_height = max(1, int(min_height))

    x = original.x
    y = original.y
    width = original.width
    height = original.height

    if handle == ResizeHandle.NONE:
        return original

    if handle == ResizeHandle.MOVE:
        moved = original.translated(delta_x, delta_y)

        if bounds is not None:
            return clamp_rect_to_bounds(moved, bounds)

        return moved

    if handle in {
        ResizeHandle.LEFT,
        ResizeHandle.TOP_LEFT,
        ResizeHandle.BOTTOM_LEFT,
    }:
        x += delta_x
        width -= delta_x

    if handle in {
        ResizeHandle.RIGHT,
        ResizeHandle.TOP_RIGHT,
        ResizeHandle.BOTTOM_RIGHT,
    }:
        width += delta_x

    if handle in {
        ResizeHandle.TOP,
        ResizeHandle.TOP_LEFT,
        ResizeHandle.TOP_RIGHT,
    }:
        y += delta_y
        height -= delta_y

    if handle in {
        ResizeHandle.BOTTOM,
        ResizeHandle.BOTTOM_LEFT,
        ResizeHandle.BOTTOM_RIGHT,
    }:
        height += delta_y

    if width < min_width:
        if handle in {
            ResizeHandle.LEFT,
            ResizeHandle.TOP_LEFT,
            ResizeHandle.BOTTOM_LEFT,
        }:
            x -= min_width - width

        width = min_width

    if height < min_height:
        if handle in {
            ResizeHandle.TOP,
            ResizeHandle.TOP_LEFT,
            ResizeHandle.TOP_RIGHT,
        }:
            y -= min_height - height

        height = min_height

    resized = Rect(
        x=int(x),
        y=int(y),
        width=int(width),
        height=int(height),
    ).normalized()

    if bounds is not None:
        resized = clamp_rect_to_bounds(resized, bounds)

    return resized


def clamp_rect_to_bounds(rect: Rect, bounds: Rect) -> Rect:
    """
    Clamp a rectangle so it remains fully inside bounds.

    If rect is larger than bounds, it is reduced to fit.
    """

    rect = rect.normalized()
    bounds = bounds.normalized()

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


def clamp_point_to_bounds(
    point_x: int,
    point_y: int,
    bounds: Rect,
) -> Tuple[int, int]:
    bounds = bounds.normalized()

    return (
        max(bounds.left, min(point_x, bounds.right)),
        max(bounds.top, min(point_y, bounds.bottom)),
    )


def rects_equal(a: Rect, b: Rect) -> bool:
    return a.normalized().as_tuple() == b.normalized().as_tuple()
