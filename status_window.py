""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Provides an always-visible BirdBros portal/status bar.

RESPONSIBILITIES:
- Display current runtime state
- Display active event/session count
- Display previous final API/result outcome
- Visually bridge the capture surface and the control panel

USED BY:
- main.py

DESIGN INTENT:
Keep application status separate from the capture overlay so status text does
not belong to the capture region or contaminate analysis/storyboard evidence.

GEOMETRY MODEL:
The portal bar is screen-relative. It begins near the left edge of the active
screen and ends just before the control panel when main.py provides panel_left.
Capture-region geometry is used only to choose the active screen and vertical
placement.
"""

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget, QGraphicsDropShadowEffect, QApplication
from PySide6.QtGui import QColor


class status_window(QWidget):
    permanent_surface_clicked = Signal()

    def __init__(
        self,
        left: int,
        top: int,
        width: int = 560,
        height: int = 48,
        panel_left: int = None
    ):
        super().__init__()

        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height
        self.panel_left = panel_left

        # Relative/clamped layout tuning. These are margins, not absolute layout
        # assumptions. Actual portal geometry derives from active screen + panel.
        self.minimum_portal_width = 420
        self.maximum_portal_height = 52
        self.minimum_portal_height = 40

        self.setWindowTitle("BirdBros Status")
        self.setObjectName("birdbros_status_window")
        self.setGeometry(
            self._portal_geometry(
                self.left,
                self.top,
                self.width_value,
                self.height_value,
                self.panel_left
            )
        )

        self.setWindowFlags(
            Qt.Window |
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.WindowDoesNotAcceptFocus
        )

        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.status_label = QLabel("Warmup | Events: 0 | Prev: None")
        self.status_label.setObjectName("statusPortal")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(max(32, self.height_value - 14))

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.status_label.setGraphicsEffect(shadow)

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 7, 8, 7)
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self._apply_visual_style()
        self.show()
        self.keep_on_top()

    def _apply_visual_style(self):
        self.setStyleSheet(
            """
            QWidget#birdbros_status_window {
                background: transparent;
            }

            QLabel#statusPortal {
                color: #F8F3E7;
                background-color: rgba(13, 15, 17, 226);
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 17px;
                font-family: "SF Pro Display", "Helvetica Neue", Arial;
                font-size: 15px;
                font-weight: 750;
                letter-spacing: 0.28px;
                padding: 8px 22px;
            }
            """
        )

    def update_status(
        self,
        current_status: str,
        active_events: int = 0,
        previous_status: str = "None"
    ):
        if not current_status:
            current_status = "Idle"

        if not previous_status:
            previous_status = "None"

        self.status_label.setText(
            f"{current_status} | Events: {active_events} | Prev: {previous_status}"
        )
        
    def keep_on_top(self):
        self.show()
        self.raise_()

    def set_status_geometry(
        self,
        left: int,
        top: int,
        width: int = 560,
        height: int = 48,
        panel_left: int = None
    ):
        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height

        if panel_left is not None:
            self.panel_left = panel_left

        self.setGeometry(
            self._portal_geometry(
                self.left,
                self.top,
                self.width_value,
                self.height_value,
                self.panel_left
            )
        )
        self.status_label.setMinimumHeight(max(32, self.height_value - 14))
        self.keep_on_top()
        
    def mousePressEvent(self, event):
        self.permanent_surface_clicked.emit()
        super().mousePressEvent(event)

    def _portal_geometry(
        self,
        left: int,
        top: int,
        width: int,
        height: int,
        panel_left: int = None
    ):
        """
        Match the status bar to the capture region.

        The status window should:
        - share the capture region's left edge
        - share the capture region's width
        - sit directly above the capture region
        """
        screen = self._screen_for_region(left, top, width, height)

        portal_left = int(left)
        portal_width = max(1, int(width))
        portal_height = self._clamp(
            int(height),
            self.minimum_portal_height,
            self.maximum_portal_height
        )

        if screen is None:
            portal_top = max(0, int(top))
        else:
            screen_rect = screen.availableGeometry()
            margin = self._clamp(
                int(screen_rect.height() * 0.012),
                8,
                16
            )

            portal_top = self._clamp(
                int(top),
                screen_rect.top() + margin,
                max(screen_rect.top() + margin, screen_rect.bottom() - portal_height - margin)
            )

        return QRect(
            portal_left,
            int(portal_top),
            portal_width,
            int(portal_height)
        )

    def _screen_for_region(self, left: int, top: int, width: int, height: int):
        app = QApplication.instance()

        if app is None:
            return None

        center = QPoint(
            int(left + (width / 2)),
            int(top + (height / 2))
        )

        screen = QApplication.screenAt(center)

        if screen is not None:
            return screen

        return QApplication.primaryScreen()

    def _clamp(self, value, minimum, maximum):
        return max(minimum, min(maximum, value))
