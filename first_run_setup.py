""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Friendly first-run setup screen for saving the user's OpenAI API key.

DESIGN INTENT:
Non-technical users should not need Terminal, .env files, or source-code edits.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFrame,
)

from api_key_store import (
    save_openai_api_key,
    looks_like_openai_api_key,
    api_key_store_error,
)


class first_run_setup_dialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.saved_api_key = ""

        self.setWindowTitle("BirdBros Recycle Co. Setup")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        card = QFrame()
        card.setObjectName("SetupCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        card_layout.setSpacing(14)

        title = QLabel("BirdBros Recycle Co.")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("First-run setup")
        subtitle.setObjectName("Subtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        explainer = QLabel(
            "BirdBros needs an OpenAI API key to analyze behavior events. "
            "Paste your key below. It will be saved securely in macOS Keychain."
        )
        explainer.setObjectName("Explainer")
        explainer.setWordWrap(True)
        explainer.setAlignment(Qt.AlignCenter)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Paste OpenAI API key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.returnPressed.connect(self._save_and_continue)

        self.show_key_button = QPushButton("Show")
        self.show_key_button.setObjectName("SecondaryButton")
        self.show_key_button.clicked.connect(self._toggle_key_visibility)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self.api_key_input, 1)
        key_row.addWidget(self.show_key_button)

        helper = QLabel("You only need to do this once on this Mac.")
        helper.setObjectName("Helper")
        helper.setAlignment(Qt.AlignCenter)

        self.save_button = QPushButton("Save & Continue")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self._save_and_continue)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setObjectName("SecondaryButton")
        self.quit_button.clicked.connect(self.reject)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(self.quit_button)
        button_row.addWidget(self.save_button)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(6)
        card_layout.addWidget(explainer)
        card_layout.addSpacing(8)
        card_layout.addLayout(key_row)
        card_layout.addWidget(helper)
        card_layout.addSpacing(8)
        card_layout.addLayout(button_row)

        root.addWidget(card)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background: #101318;
                color: #F2F4F8;
                font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial;
            }

            QFrame#SetupCard {
                background: rgba(30, 34, 42, 0.96);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 22px;
            }

            QLabel#Title {
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 0.4px;
            }

            QLabel#Subtitle {
                color: #9EE7D7;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 1.5px;
                text-transform: uppercase;
            }

            QLabel#Explainer {
                color: rgba(242, 244, 248, 0.82);
                font-size: 14px;
                line-height: 1.35em;
            }

            QLabel#Helper {
                color: rgba(242, 244, 248, 0.55);
                font-size: 12px;
            }

            QLineEdit {
                background: rgba(255, 255, 255, 0.08);
                color: #F2F4F8;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 12px;
                padding: 11px 12px;
                font-size: 13px;
                selection-background-color: #65D7C0;
            }

            QLineEdit:focus {
                border: 1px solid rgba(101, 215, 192, 0.85);
                background: rgba(255, 255, 255, 0.11);
            }

            QPushButton {
                min-height: 34px;
                border-radius: 14px;
                padding: 8px 14px;
                font-weight: 650;
            }

            QPushButton#PrimaryButton {
                background: #65D7C0;
                color: #07110F;
                border: none;
            }

            QPushButton#PrimaryButton:hover {
                background: #7BE4D0;
            }

            QPushButton#SecondaryButton {
                background: rgba(255, 255, 255, 0.08);
                color: rgba(242, 244, 248, 0.86);
                border: 1px solid rgba(255, 255, 255, 0.12);
            }

            QPushButton#SecondaryButton:hover {
                background: rgba(255, 255, 255, 0.13);
            }
        """)

    def _toggle_key_visibility(self):
        if self.api_key_input.echoMode() == QLineEdit.Password:
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.show_key_button.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.show_key_button.setText("Show")

    def _save_and_continue(self):
        api_key = self.api_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "API key needed", "Paste your OpenAI API key to continue.")
            return

        if not looks_like_openai_api_key(api_key):
            reply = QMessageBox.question(
                self,
                "Double-check key",
                "This does not look like a typical OpenAI API key. Save it anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

        try:
            save_openai_api_key(api_key)
        except api_key_store_error as exc:
            QMessageBox.critical(
                self,
                "Could not save key",
                f"BirdBros could not save the key to macOS Keychain.\n\n{exc}"
            )
            return

        self.saved_api_key = api_key
        self.accept()


def run_first_run_setup(parent=None):
    dialog = first_run_setup_dialog(parent=parent)

    if dialog.exec() == QDialog.Accepted:
        return dialog.saved_api_key

    return ""


