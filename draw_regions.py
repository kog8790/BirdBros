"""
draw_regions.py

Region selection and live editable-region interaction helpers for BirdBros.

This file currently has two responsibilities:

1. RegionDragCaptureDialog
   Transitional one-shot drag-to-draw dialog used by the existing Draw Capture /
   Draw Trigger buttons.

2. LiveRegionInteraction
   Qt-agnostic interaction controller for the newer always-aware overlay model.
   It translates mouse hover/press/drag/release gestures into updated
   CaptureRegion / ROI geometry.

The long-term direction is for LiveRegionInteraction to replace the old
RegionDragCaptureDialog flow once overlay_window.py is wired for live editing.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, Optional, Tuple

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from capture_regions import CaptureRegion
from roi_regions import ROI
from mouse_tools import (
    Rect,
    ResizeHandle,
    clamp_rect_to_bounds,
    cursor_role_for_handle,
    detect_resize_handle,
    resize_rect_from_drag,
)


Point = Tuple[int, int]
RectTuple = Tuple[int, int, int, int]

CAPTURE_TARGET_KEY = "capture_region"


class RegionDragCaptureDialog(QDialog):
    """
    Full-screen translucent overlay used to select a rectangular screen region.

    Output:
        selected_rect = (screen_x, screen_y, width, height)

    This remains for compatibility with the current Draw Capture / Draw Trigger
    buttons while live region editing is being built.
    """

    def __init__(self, title, instructions, parent=None):
        super().__init__(parent)

        self.selected_rect = None
        self._drag_start = None
        self._drag_current = None

        self.setWindowTitle(title)
        self.setModal(True)
        self.setMouseTracking(True)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._apply_virtual_screen_geometry()
        self._build_instruction_card(title, instructions)

    def _apply_virtual_screen_geometry(self):
        screen = QApplication.primaryScreen()

        if not screen:
            return

        self.setGeometry(screen.virtualGeometry())

    def _build_instruction_card(self, title, instructions):
        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(0, 18, 0, 0)
        overlay_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        card = QGroupBox(title)
        card.setObjectName("capturePositionCard")
        card.setMinimumWidth(420)
        card.setMaximumWidth(560)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(8)

        instruction_label = QLabel(instructions)
        instruction_label.setWordWrap(True)

        hint_label = QLabel("Drag to draw. Release to accept. Press Esc to cancel.")
        hint_label.setWordWrap(True)

        card_layout.addWidget(instruction_label)
        card_layout.addWidget(hint_label)

        overlay_layout.addWidget(card)

    def _current_local_rect(self):
        if self._drag_start is None or self._drag_current is None:
            return QRect()

        return QRect(self._drag_start, self._drag_current).normalized()

    def _local_rect_to_global_tuple(self, rect):
        window_origin = self.geometry().topLeft()

        return (
            int(window_origin.x() + rect.x()),
            int(window_origin.y() + rect.y()),
            int(rect.width()),
            int(rect.height()),
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        self._drag_start = event.position().toPoint()
        self._drag_current = self._drag_start
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_start is None:
            return

        self._drag_current = event.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or self._drag_start is None:
            return

        self._drag_current = event.position().toPoint()
        rect = self._current_local_rect()

        if rect.width() < 8 or rect.height() < 8:
            self._drag_start = None
            self._drag_current = None
            self.update()
            return

        self.selected_rect = self._local_rect_to_global_tuple(rect)
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 78))

        rect = self._current_local_rect()

        if rect.isNull():
            return

        painter.fillRect(rect, QColor(116, 215, 196, 38))

        pen = QPen(QColor(116, 215, 196, 230))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawRect(rect)


@dataclass(frozen=True)
class EditableRegion:
    """
    Screen-space editable region used by the live overlay interaction layer.
    """

    key: str
    label: str
    rect: Rect
    kind: str
    roi: Optional[ROI] = None
    editable: bool = True
    movable: bool = True
    resizable: bool = True
    bounds: Optional[Rect] = None

    @property
    def is_capture(self) -> bool:
        return self.kind == "capture"

    @property
    def is_roi(self) -> bool:
        return self.kind == "roi"


@dataclass(frozen=True)
class RegionHover:
    target_key: Optional[str] = None
    handle: str = ResizeHandle.NONE
    cursor_role: str = "default"

    @property
    def has_target(self) -> bool:
        return self.target_key is not None and self.handle != ResizeHandle.NONE

    @property
    def is_resize(self) -> bool:
        return self.handle not in (ResizeHandle.NONE, ResizeHandle.MOVE)

    @property
    def is_move(self) -> bool:
        return self.handle == ResizeHandle.MOVE


@dataclass(frozen=True)
class RegionDrag:
    target_key: str
    handle: str
    start_point: Point
    original_rect: Rect


@dataclass(frozen=True)
class RegionEditResult:
    """
    Returned on mouse release when an edit has been committed.
    """

    capture_region: CaptureRegion
    rois: Dict[str, ROI]
    changed_key: Optional[str]


@dataclass(frozen=True)
class RegionPreviewState:
    """
    Screen-space rectangles for overlay painting while hovering or dragging.
    """

    capture_rect: Rect
    roi_rects: Dict[str, Rect]
    hover: RegionHover
    drag: Optional[RegionDrag]


class LiveRegionInteraction:
    """
    Stateful interaction controller for live editable overlay regions.

    Qt event handling belongs in overlay_window.py. This class only decides
    hover target, drag target, preview geometry, and committed geometry.
    """

    def __init__(
        self,
        capture_region: CaptureRegion,
        rois: Iterable[ROI],
        *,
        edge_margin: int = 8,
        min_capture_width: int = 80,
        min_capture_height: int = 80,
        min_roi_width: int = 20,
        min_roi_height: int = 20,
        preserve_roi_percent_on_capture_resize: bool = True,
    ):
        self.capture_region = capture_region
        self.rois: Dict[str, ROI] = {roi.key: roi for roi in rois}

        self.edge_margin = edge_margin
        self.min_capture_width = min_capture_width
        self.min_capture_height = min_capture_height
        self.min_roi_width = min_roi_width
        self.min_roi_height = min_roi_height
        self.preserve_roi_percent_on_capture_resize = (
            preserve_roi_percent_on_capture_resize
        )

        self.hover = RegionHover()
        self.drag: Optional[RegionDrag] = None

        self._preview_capture_region = capture_region
        self._preview_rois: Dict[str, ROI] = dict(self.rois)

    @property
    def is_dragging(self) -> bool:
        return self.drag is not None

    def set_regions(
        self,
        capture_region: CaptureRegion,
        rois: Iterable[ROI],
    ) -> None:
        """
        Replace the editable model from outside state.

        Use this when config/control panel changed independently from dragging.
        Does not interrupt an active drag.
        """

        if self.drag is not None:
            return

        self.capture_region = capture_region
        self.rois = {roi.key: roi for roi in rois}
        self._preview_capture_region = capture_region
        self._preview_rois = dict(self.rois)
        self.hover = RegionHover()

    def hover_at_screen_point(self, x: int, y: int) -> RegionHover:
        """
        Update hover state from a global/screen-space mouse point.
        """

        if self.drag is not None:
            return self.hover

        for region in self._editable_regions_for_current_preview():
            handle = self._detect_handle_for_region(x, y, region)

            if handle != ResizeHandle.NONE:
                self.hover = RegionHover(
                    target_key=region.key,
                    handle=handle,
                    cursor_role=cursor_role_for_handle(handle),
                )
                return self.hover

        self.hover = RegionHover()
        return self.hover

    def begin_drag_at_screen_point(self, x: int, y: int) -> Optional[RegionDrag]:
        """
        Begin editing if the mouse is over an editable target.
        """

        hover = self.hover_at_screen_point(x, y)

        if not hover.has_target:
            return None

        region = self._editable_region_by_key(hover.target_key)
        if region is None:
            return None

        self.drag = RegionDrag(
            target_key=region.key,
            handle=hover.handle,
            start_point=(x, y),
            original_rect=region.rect,
        )
        return self.drag

    def drag_to_screen_point(self, x: int, y: int) -> Optional[RegionPreviewState]:
        """
        Update preview geometry while dragging.

        Returns preview state for immediate overlay repaint.
        """

        if self.drag is None:
            return None

        delta_x = x - self.drag.start_point[0]
        delta_y = y - self.drag.start_point[1]

        if self.drag.target_key == CAPTURE_TARGET_KEY:
            self._drag_capture_region(delta_x, delta_y)
        else:
            self._drag_roi(self.drag.target_key, delta_x, delta_y)

        return self.get_preview_state()

    def finish_drag(self) -> Optional[RegionEditResult]:
        """
        Commit preview state and return changed region objects.
        """

        if self.drag is None:
            return None

        changed_key = self.drag.target_key

        self.capture_region = self._preview_capture_region
        self.rois = dict(self._preview_rois)

        result = RegionEditResult(
            capture_region=self.capture_region,
            rois=dict(self.rois),
            changed_key=changed_key,
        )

        self.drag = None
        self.hover = RegionHover()

        return result

    def cancel_drag(self) -> None:
        """
        Discard preview state and return to committed geometry.
        """

        self._preview_capture_region = self.capture_region
        self._preview_rois = dict(self.rois)
        self.drag = None
        self.hover = RegionHover()

    def get_preview_state(self) -> RegionPreviewState:
        """
        Return screen-space rectangles for overlay painting.
        """

        capture_rect = self._capture_region_to_rect(self._preview_capture_region)

        roi_rects = {
            key: self._roi_to_screen_rect(roi, self._preview_capture_region)
            for key, roi in self._preview_rois.items()
        }

        return RegionPreviewState(
            capture_rect=capture_rect,
            roi_rects=roi_rects,
            hover=self.hover,
            drag=self.drag,
        )

    def get_editable_regions(self) -> Tuple[EditableRegion, ...]:
        """
        Return current editable regions for debugging/tests/overlay inspection.
        """

        return self._editable_regions_for_current_preview()

    def _drag_capture_region(self, delta_x: int, delta_y: int) -> None:
        if self.drag is None:
            return

        updated_rect = resize_rect_from_drag(
            original=self.drag.original_rect,
            handle=self.drag.handle,
            delta_x=delta_x,
            delta_y=delta_y,
            min_width=self.min_capture_width,
            min_height=self.min_capture_height,
            bounds=None,
        )

        old_capture = self.capture_region
        new_capture = self._rect_to_capture_region(updated_rect)

        self._preview_capture_region = new_capture

        if self.preserve_roi_percent_on_capture_resize:
            self._preview_rois = self._scale_rois_between_capture_regions(
                old_capture,
                new_capture,
                self.rois,
            )
        else:
            self._preview_rois = self._move_rois_with_capture_origin(
                new_capture,
                self.rois,
            )

    def _drag_roi(self, target_key: str, delta_x: int, delta_y: int) -> None:
        if self.drag is None:
            return

        roi = self._preview_rois.get(target_key)
        if roi is None:
            return

        capture = self._preview_capture_region
        capture_bounds = self._capture_region_to_rect(capture)

        updated_screen_rect = resize_rect_from_drag(
            original=self.drag.original_rect,
            handle=self.drag.handle,
            delta_x=delta_x,
            delta_y=delta_y,
            min_width=self.min_roi_width,
            min_height=self.min_roi_height,
            bounds=capture_bounds,
        )

        updated_screen_rect = clamp_rect_to_bounds(
            updated_screen_rect,
            capture_bounds,
        )

        updated_roi = ROI.from_screen_tuple_relative_to_capture(
            key=roi.key,
            label=roi.label,
            rect_tuple=updated_screen_rect.as_tuple(),
            capture_region=capture,
            roles=set(roi.roles),
        )

        self._preview_rois[target_key] = updated_roi

    def _editable_regions_for_current_preview(self) -> Tuple[EditableRegion, ...]:
        capture = self._preview_capture_region
        capture_rect = self._capture_region_to_rect(capture)

        roi_regions = []

        for roi in self._preview_rois.values():
            if not roi.is_editable:
                continue

            roi_regions.append(
                EditableRegion(
                    key=roi.key,
                    label=roi.label,
                    rect=self._roi_to_screen_rect(roi, capture),
                    kind="roi",
                    roi=roi,
                    editable=roi.is_editable,
                    bounds=capture_rect,
                )
            )

        capture_editable_region = EditableRegion(
            key=CAPTURE_TARGET_KEY,
            label="Capture Region",
            rect=capture_rect,
            kind="capture",
            bounds=None,
        )

        # ROI first so trigger/object/subject handles win over capture handles.
        return tuple(roi_regions + [capture_editable_region])

    def _editable_region_by_key(self, key: Optional[str]) -> Optional[EditableRegion]:
        if key is None:
            return None

        for region in self._editable_regions_for_current_preview():
            if region.key == key:
                return region

        return None

    def _detect_handle_for_region(
        self,
        x: int,
        y: int,
        region: EditableRegion,
    ) -> str:
        if not region.editable:
            return ResizeHandle.NONE

        handle = detect_resize_handle(
            point_x=x,
            point_y=y,
            rect=region.rect,
            edge_margin=self.edge_margin,
        )

        if handle == ResizeHandle.NONE:
            return ResizeHandle.NONE

        if handle == ResizeHandle.MOVE and not region.movable:
            return ResizeHandle.NONE

        if handle != ResizeHandle.MOVE and not region.resizable:
            return ResizeHandle.NONE

        return handle

    def _scale_rois_between_capture_regions(
        self,
        old_capture: CaptureRegion,
        new_capture: CaptureRegion,
        rois: Dict[str, ROI],
    ) -> Dict[str, ROI]:
        """
        Preserve ROI percentages when capture region changes.
        """

        scaled = {}

        old_width = max(1, old_capture.width)
        old_height = max(1, old_capture.height)

        for key, roi in rois.items():
            x_pct = roi.x / old_width
            y_pct = roi.y / old_height
            width_pct = roi.width / old_width
            height_pct = roi.height / old_height

            scaled_roi = replace(
                roi,
                x=int(round(x_pct * new_capture.width)),
                y=int(round(y_pct * new_capture.height)),
                width=max(1, int(round(width_pct * new_capture.width))),
                height=max(1, int(round(height_pct * new_capture.height))),
            )

            scaled_roi.clamp_to_capture(new_capture)
            scaled[key] = scaled_roi

        return scaled

    def _move_rois_with_capture_origin(
        self,
        new_capture: CaptureRegion,
        rois: Dict[str, ROI],
    ) -> Dict[str, ROI]:
        """
        Preserve local pixel ROI values when capture region changes.
        """

        moved = {}

        for key, roi in rois.items():
            moved_roi = replace(roi)
            moved_roi.clamp_to_capture(new_capture)
            moved[key] = moved_roi

        return moved

    def _capture_region_to_rect(self, capture_region: CaptureRegion) -> Rect:
        return Rect(
            capture_region.left,
            capture_region.top,
            capture_region.width,
            capture_region.height,
        )

    def _rect_to_capture_region(self, rect: Rect) -> CaptureRegion:
        region = CaptureRegion(
            left=rect.x,
            top=rect.y,
            width=rect.width,
            height=rect.height,
        )
        region.clamp_size()
        return region

    def _roi_to_screen_rect(self, roi: ROI, capture_region: CaptureRegion) -> Rect:
        x, y, width, height = roi.to_screen_tuple(capture_region)
        return Rect(x, y, width, height)
