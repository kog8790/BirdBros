""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Provides a small always-visible Bird Bros status window.

RESPONSIBILITIES:
- Display current runtime state
- Display active event/session count
- Display previous final API/result outcome

USED BY:
- main.py

DESIGN INTENT:
Keep application status separate from the capture overlay so status text does
not belong to the capture region or contaminate analysis/storyboard evidence.
"""

from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget


class status_window(QWidget):
    def __init__(
        self,
        left: int,
        top: int,
        width: int = 560,
        height: int = 42
    ):
        super().__init__()

        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height

        self.setWindowTitle("Bird Bros Status")
        self.setGeometry(QRect(self.left, self.top, self.width_value, self.height_value))

        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.FramelessWindowHint
        )

        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.status_label = QLabel("Warmup | Events: 0 | Prev: None")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.status_label.setStyleSheet(
            """
            QLabel {
                color: white;
                background-color: rgb(40, 40, 40);
                font-size: 14px;
                font-weight: 600;
                padding: 8px;
                border-radius: 6px;
            }
            """
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self.status_label)

        self.setLayout(layout)
        self.show()
        self.keep_on_top()

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
        self.keep_on_top()

    def keep_on_top(self):
        self.show()
        self.raise_()

    def set_status_geometry(
        self,
        left: int,
        top: int,
        width: int = 560,
        height: int = 42
    ):
        self.left = left
        self.top = top
        self.width_value = width
        self.height_value = height
        self.setGeometry(QRect(self.left, self.top, self.width_value, self.height_value))
        self.keep_on_top()

