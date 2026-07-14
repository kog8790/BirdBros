from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)


class RegionDragCaptureDialog(QDialog):
    """
    Full-screen translucent overlay used to select a rectangular screen region.

    Output:
        selected_rect = (screen_x, screen_y, width, height)

    The returned coordinates are global screen coordinates, not local widget
    coordinates. The caller is responsible for converting those coordinates
    into capture-region-relative ROI values when needed.
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

