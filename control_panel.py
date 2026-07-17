""" ### SEGMENT: FILE OVERVIEW ###
PURPOSE:
Provides a PySide6 control panel for real-time Bird Bros configuration.

RESPONSIBILITIES:
- Edit capture region and ROI values
- Configure display toggles
- Configure motion sensitivity
- Configure prompt/task labels
- Configure reward behavior
- Emit live config updates to main.py

DESIGN INTENT:
Allow open-source users to tune both system geometry and AI task wording without code edits.
"""

import json
import os

try:
    import pyautogui
except ImportError:
    pyautogui = None

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QCursor, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QMessageBox,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton
)

from config_manager import DEFAULT_CONFIG, load_config, save_config
from control_panel_ui import control_panel_ui
from capture_regions import CaptureRegion
from draw_regions import RegionDragCaptureDialog
from roi_regions import ROI
from macos_permissions import (
    accessibility_trusted,
    request_accessibility_trust,
    open_accessibility_settings,
)

class MousePositionCaptureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.captured_position = None

        self.setWindowTitle("Capture Mouse Position")
        self.setModal(True)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.virtualGeometry())

        overlay_layout = QVBoxLayout(self)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setAlignment(Qt.AlignCenter)

        card = QGroupBox("Capture Mouse Position")
        card.setObjectName("capturePositionCard")
        card.setMinimumWidth(380)
        card.setMaximumWidth(460)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        instructions = QLabel(
            "Move your mouse to the target location.\n"
            "Click once anywhere on screen to capture that position.\n"
            "Press Esc to cancel."
        )
        instructions.setWordWrap(True)

        self.position_label = QLabel("Current position: —")
        self.screen_label = QLabel("Screen: —")
        self.status_label = QLabel("Status: —")

        card_layout.addWidget(instructions)
        card_layout.addWidget(self.position_label)
        card_layout.addWidget(self.screen_label)
        card_layout.addWidget(self.status_label)

        overlay_layout.addWidget(card)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_position)
        self.timer.start(50)

        self._refresh_position()

    def _refresh_position(self):
        if pyautogui is None:
            self.position_label.setText("Current position: unavailable")
            self.screen_label.setText("Screen: unavailable")
            self.status_label.setText("Status: pyautogui is not available")
            return

        x, y = pyautogui.position()
        width, height = pyautogui.size()
        on_screen = pyautogui.onScreen(x, y)

        self.position_label.setText(f"Current position: x={x}, y={y}")
        self.screen_label.setText(f"Screen: {width} × {height}")
        self.status_label.setText(
            f"Status: {'valid on-screen coordinate' if on_screen else 'outside screen bounds'}"
        )

    def mousePressEvent(self, event):
        if pyautogui is None:
            self.reject()
            return

        x, y = pyautogui.position()

        if not pyautogui.onScreen(x, y):
            return

        self.captured_position = (int(x), int(y))
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return

        super().keyPressEvent(event)
        
class control_panel(QWidget, control_panel_ui):
    config_changed = Signal(dict)
    exit_requested = Signal()
    manual_capture_requested = Signal()
    detection_paused_changed = Signal(bool)
    permanent_surface_clicked = Signal()

    def __init__(self, config_path=None):
        super().__init__()

        self.config_path = config_path
        self.config = load_config(self.config_path)
        self.detection_paused = True
        self._rebuilding_click_sequence = False

        self.setWindowTitle("Bird Bros Control Panel")
        self.setObjectName("birdbros_control_panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._apply_responsive_window_size()
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        self._build_ui()
        self._apply_visual_style()
        self._load_config_into_widgets()
        self._connect_signals()
        self.emit_config()

    # ================================
    # UI CONSTRUCTION
    # ================================

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        capture_group = QGroupBox("Capture Region")
        capture_form = QFormLayout()

        self.capture_left = self._make_spinbox(0, 10000)
        self.capture_top = self._make_spinbox(0, 10000)
        self.capture_width = self._make_spinbox(1, 10000)
        self.capture_height = self._make_spinbox(1, 10000)

        capture_form.addRow("Left", self.capture_left)
        capture_form.addRow("Top", self.capture_top)
        capture_form.addRow("Width", self.capture_width)
        capture_form.addRow("Height", self.capture_height)
        capture_group.setLayout(capture_form)
        
        video_group = QGroupBox("Video Input")
        video_layout = QVBoxLayout()
        video_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        video_layout.setSpacing(10)

        self.video_mode = QComboBox()
        self.video_mode.addItems(["screen_capture", "video_file"])

        self.video_path = QLineEdit()
        self.video_path.setPlaceholderText("/path/to/video.mp4")

        self.video_loop = QCheckBox("Loop Video")
        self.video_fps = self._make_spinbox(1, 120)

        self.video_mode_row = self._make_reward_row("Mode", self.video_mode)
        self.video_path_row = self._make_reward_row("Video Path", self.video_path)
        self.video_loop_row = self._make_reward_row("Loop", self.video_loop)
        self.video_fps_row = self._make_reward_row("FPS", self.video_fps)

        video_layout.addWidget(self.video_mode_row)
        video_layout.addWidget(self.video_path_row)
        video_layout.addWidget(self.video_loop_row)
        video_layout.addWidget(self.video_fps_row)

        video_group.setLayout(video_layout)

        self.subject_group = QGroupBox("Subject ROI")
        subject_form = QFormLayout()

        self.subject_x = self._make_spinbox(0, 10000)
        self.subject_y = self._make_spinbox(0, 10000)
        self.subject_w = self._make_spinbox(1, 10000)
        self.subject_h = self._make_spinbox(1, 10000)

        subject_form.addRow("X", self.subject_x)
        subject_form.addRow("Y", self.subject_y)
        subject_form.addRow("W", self.subject_w)
        subject_form.addRow("H", self.subject_h)
        self.subject_group.setLayout(subject_form)

        self.object_group = QGroupBox("Trigger ROI")
        object_form = QFormLayout()

        self.object_x = self._make_spinbox(0, 10000)
        self.object_y = self._make_spinbox(0, 10000)
        self.object_w = self._make_spinbox(1, 10000)
        self.object_h = self._make_spinbox(1, 10000)

        object_form.addRow("X", self.object_x)
        object_form.addRow("Y", self.object_y)
        object_form.addRow("W", self.object_w)
        object_form.addRow("H", self.object_h)
        self.object_group.setLayout(object_form)

        motion_group = QGroupBox("Motion")
        motion_form = QFormLayout()

        self.motion_min_area = self._make_spinbox(100, 50000)
        motion_form.addRow("Motion Sensitivity", self.motion_min_area)
        motion_group.setLayout(motion_form)

        display_group = QGroupBox("Display")
        display_layout = QGridLayout()
        display_layout.setSpacing(10)

        self.show_overlay = QCheckBox("Show Overlay")
        self.show_grid = QCheckBox("Show Grid")
        self.show_coords = QCheckBox("Show Coordinates")
        self.show_capture_border = QCheckBox("Show Capture Border")
        self.show_labels = QCheckBox("Show Labels")

        display_layout.addWidget(self.show_overlay, 0, 0)
        display_layout.addWidget(self.show_grid, 0, 1)

        display_layout.addWidget(self.show_capture_border, 1, 0)
        display_layout.addWidget(self.show_labels, 1, 1)

        display_layout.addWidget(self.show_coords, 2, 0, 1, 2)

        display_layout.setColumnStretch(0, 1)
        display_layout.setColumnStretch(1, 1)

        display_group.setLayout(display_layout)

        task_group = QGroupBox("AI Task Labels")
        task_form = QFormLayout()

        self.behavior_mode = QComboBox()
        self.behavior_mode.setObjectName("behaviorModeCombo")
        self.behavior_mode.addItems(["simple", "advanced"])
        self.behavior_mode.setMinimumWidth(210)
        self.behavior_mode.setMaximumWidth(210)
        self.behavior_mode.view().setMinimumWidth(210)

        self.reward_description = QLineEdit()
        self.reward_description.setCursorPosition(0)
        self.reward_description.setPlaceholderText(
            "A bird drops litter into a receptacle."
        )

        self.subject_label = QLineEdit()
        self.object_label = QLineEdit()
        self.target_zone_label = QLineEdit()
        self.action_label = QLineEdit()

        self.subject_label.setPlaceholderText("non-human animal")
        self.object_label.setPlaceholderText("man-made litter or trash")
        self.target_zone_label.setPlaceholderText("trash receptacle")
        self.action_label.setPlaceholderText("depositing")

        self.subject_label_widget = QLabel("Subject")
        self.object_label_widget = QLabel("Object")
        self.target_zone_label_widget = QLabel("Target Zone")
        self.action_label_widget = QLabel("Action")

        behavior_mode_row = QWidget()
        behavior_mode_layout = QGridLayout(behavior_mode_row)
        behavior_mode_layout.setContentsMargins(0, 0, 0, 0)
        behavior_mode_layout.setHorizontalSpacing(0)
        behavior_mode_layout.setVerticalSpacing(8)

        behavior_mode_label = QLabel("Behavior Mode")
        behavior_mode_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        behavior_mode_layout.addWidget(
            behavior_mode_label,
            0,
            0,
            1,
            3,
            Qt.AlignLeft | Qt.AlignVCenter
        )

        behavior_mode_layout.addWidget(
            self.behavior_mode,
            1,
            1,
            Qt.AlignCenter
        )

        behavior_mode_layout.setColumnStretch(0, 1)
        behavior_mode_layout.setColumnStretch(1, 0)
        behavior_mode_layout.setColumnStretch(2, 1)

        task_form.addRow(behavior_mode_row)

        reward_when_label = QLabel("Reward When")
        reward_when_label.setAlignment(Qt.AlignLeft)

        task_form.addRow(reward_when_label)
        task_form.addRow(self.reward_description)

        task_form.addRow(self.subject_label_widget, self.subject_label)
        task_form.addRow(self.object_label_widget, self.object_label)
        task_form.addRow(self.target_zone_label_widget, self.target_zone_label)
        task_form.addRow(self.action_label_widget, self.action_label)

        task_group.setLayout(task_form)

        reward_group = QGroupBox("Reward Action")
        reward_layout = QVBoxLayout()
        reward_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        reward_layout.setSpacing(10)

        self.reward_mode = QComboBox()
        self.reward_mode.addItems(["overlay_status", "mouse_click", "keyboard_shortcut", "webhook", "shell_command"])

        # Legacy/default mouse-click widgets.
        # These remain available internally so older configs can still load cleanly,
        # but mouse_click mode now uses the dynamic click-sequence UI below.
        self.reward_x = self._make_spinbox(0, 10000)
        self.reward_y = self._make_spinbox(0, 10000)
        self.reward_clicks = self._make_spinbox(0, 99)
        self.reward_interval_ms = self._make_spinbox(0, 10000)
        self.reward_move_duration_ms = self._make_spinbox(0, 10000)

        self.reward_click_sequence_widgets = []
        self.reward_click_sequence_container = QWidget()
        self.reward_click_sequence_layout = QVBoxLayout(self.reward_click_sequence_container)
        self.reward_click_sequence_layout.setContentsMargins(0, 0, 0, 0)
        self.reward_click_sequence_layout.setSpacing(8)

        self.reward_keys = QLineEdit()
        self.reward_keys.setPlaceholderText("command,space")

        self.reward_command = QLineEdit()
        self.reward_command.setPlaceholderText("open /System/Applications/Calculator.app")

        self.reward_url = QLineEdit()
        self.reward_url.setPlaceholderText("https://example.com/webhook")

        self.reward_method = QComboBox()
        self.reward_method.addItems(["POST", "GET"])

        self.reward_timeout = self._make_spinbox(1, 300)

        self.reward_bearer_token = QLineEdit()
        self.reward_bearer_token.setPlaceholderText("optional bearer token")

        self.reward_headers = QLineEdit()
        self.reward_headers.setPlaceholderText('optional JSON: {"X-Source":"BirdBros"}')

        self.reward_payload = QLineEdit()
        self.reward_payload.setPlaceholderText('optional JSON: {"event":"reward"}')

        self.reward_mode_row = self._make_reward_row("Mode", self.reward_mode)
        self.reward_x_row = self._make_reward_row("Mouse X", self.reward_x)
        self.reward_y_row = self._make_reward_row("Mouse Y", self.reward_y)
        self.reward_clicks_row = self._make_reward_row("Mouse Clicks", self.reward_clicks)
        self.reward_interval_row = self._make_reward_row("Click Interval (ms)", self.reward_interval_ms)
        self.reward_move_duration_row = self._make_reward_row("Move Duration (ms)", self.reward_move_duration_ms)
        self.reward_click_sequence_row = self._make_full_width_reward_row("Click Sequence", self.reward_click_sequence_container)
        self.reward_keys_row = self._make_reward_row("Shortcut Keys", self.reward_keys)
        self.reward_command_row = self._make_reward_row("Shell Command", self.reward_command)
        self.reward_url_row = self._make_reward_row("Webhook URL", self.reward_url)
        self.reward_method_row = self._make_reward_row("Webhook Method", self.reward_method)
        self.reward_timeout_row = self._make_reward_row("Webhook Timeout (s)", self.reward_timeout)
        self.reward_bearer_row = self._make_reward_row("Bearer Token", self.reward_bearer_token)
        self.reward_headers_row = self._make_reward_row("Headers JSON", self.reward_headers)
        self.reward_payload_row = self._make_reward_row("Payload JSON", self.reward_payload)

        reward_layout.addWidget(self.reward_mode_row)
        reward_layout.addWidget(self.reward_x_row)
        reward_layout.addWidget(self.reward_y_row)
        reward_layout.addWidget(self.reward_clicks_row)
        reward_layout.addWidget(self.reward_interval_row)
        reward_layout.addWidget(self.reward_move_duration_row)
        reward_layout.addWidget(self.reward_click_sequence_row)
        reward_layout.addWidget(self.reward_keys_row)
        reward_layout.addWidget(self.reward_command_row)
        reward_layout.addWidget(self.reward_url_row)
        reward_layout.addWidget(self.reward_method_row)
        reward_layout.addWidget(self.reward_timeout_row)
        reward_layout.addWidget(self.reward_bearer_row)
        reward_layout.addWidget(self.reward_headers_row)
        reward_layout.addWidget(self.reward_payload_row)

        reward_group.setLayout(reward_layout)

        task_group.setTitle("Behavior")
        reward_group.setTitle("Reward Action")

        button_grid = QGridLayout()
        button_grid.setSpacing(8)

        self.start_pause_button = QPushButton("Start Detection")
        self.draw_capture_button = QPushButton("Draw Capture")
        self.draw_trigger_button = QPushButton("Draw Trigger")
        self.save_button = QPushButton("Save")
        self.reload_button = QPushButton("Reload")
        self.reset_button = QPushButton("Reset")
        self.manual_capture_button = QPushButton("Snapshot")
        self.exit_button = QPushButton("Exit")

        for button in [
            self.start_pause_button,
            self.draw_capture_button,
            self.draw_trigger_button,
            self.save_button,
            self.reload_button,
            self.reset_button,
            self.manual_capture_button,
            self.exit_button
        ]:
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.start_pause_button.setObjectName("primaryButton")
        self.exit_button.setObjectName("dangerButton")
        self.draw_capture_button.setObjectName("secondaryButton")
        self.draw_trigger_button.setObjectName("secondaryButton")
        self.save_button.setObjectName("secondaryButton")
        self.reload_button.setObjectName("secondaryButton")
        self.reset_button.setObjectName("secondaryButton")
        self.manual_capture_button.setObjectName("secondaryButton")

        button_grid.addWidget(self.start_pause_button, 0, 0, 1, 2)
        button_grid.addWidget(self.draw_capture_button, 1, 0)
        button_grid.addWidget(self.draw_trigger_button, 1, 1)
        button_grid.addWidget(self.save_button, 2, 0)
        button_grid.addWidget(self.reload_button, 2, 1)
        button_grid.addWidget(self.manual_capture_button, 3, 0)
        button_grid.addWidget(self.reset_button, 3, 1)
        button_grid.addWidget(self.exit_button, 4, 0, 1, 2)

        button_grid.setColumnStretch(0, 1)
        button_grid.setColumnStretch(1, 1)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("footerStatus")
        self.status_label.setAlignment(Qt.AlignCenter)

        for group in [
            capture_group, video_group, self.subject_group, self.object_group,
            motion_group, display_group, task_group, reward_group
        ]:
            group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        capture_group.setTitle("")
        video_group.setTitle("")
        self.subject_group.setTitle("")
        self.object_group.setTitle("")
        motion_group.setTitle("")
        display_group.setTitle("")

        main_layout.addWidget(self._make_sidebar_header())
        main_layout.addWidget(task_group)
        main_layout.addWidget(reward_group)

        self.display_options_section = self._make_collapsible_section(
            "Display Options",
            display_group,
            expanded=False,
            icon_text="EYE"
        )
        main_layout.addWidget(self.display_options_section)

        self.capture_region_section = self._make_collapsible_section(
            "Capture Region",
            capture_group,
            expanded=False,
            icon_text="CAP"
        )
        main_layout.addWidget(self.capture_region_section)

        self.video_input_section = self._make_collapsible_section(
            "Video Input",
            video_group,
            expanded=False,
            icon_text="VID"
        )
        main_layout.addWidget(self.video_input_section)

        self.object_roi_section = self._make_collapsible_section(
            "Trigger ROI",
            self.object_group,
            expanded=False,
            icon_text="ROI"
        )
        main_layout.addWidget(self.object_roi_section)

        self.subject_roi_section = self._make_collapsible_section(
            "Subject ROI",
            self.subject_group,
            expanded=False,
            icon_text="SUB"
        )
        main_layout.addWidget(self.subject_roi_section)

        self.motion_section = self._make_collapsible_section(
            "Motion",
            motion_group,
            expanded=False,
            icon_text="MTN"
        )
        main_layout.addWidget(self.motion_section)

        main_layout.addLayout(button_grid)
        main_layout.addWidget(self.status_label)

        content_widget = QWidget()
        content_widget.setMinimumWidth(0)
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        content_widget.setLayout(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(8)
        outer_layout.addWidget(scroll)

        self.setLayout(outer_layout)    

    # ================================
    # SIGNAL WIRING
    # ================================

    def _connect_signals(self):
        spinboxes = [
            self.capture_left, self.capture_top, self.capture_width, self.capture_height,
            self.subject_x, self.subject_y, self.subject_w, self.subject_h,
            self.object_x, self.object_y, self.object_w, self.object_h,
            self.motion_min_area,
            self.reward_x, self.reward_y,
            self.reward_interval_ms, self.reward_move_duration_ms,
            self.reward_timeout
        ]
        for widget in spinboxes:
            widget.valueChanged.connect(self._on_widget_changed)

        checkboxes = [
            self.show_overlay,
            self.show_grid,
            self.show_coords,
            self.show_capture_border,
            self.show_labels
        ]

        for widget in checkboxes:
            widget.stateChanged.connect(self._on_widget_changed)

        self.reward_mode.currentTextChanged.connect(self._on_reward_action_changed)
        self.reward_method.currentIndexChanged.connect(self._on_widget_changed)

        self.behavior_mode.currentTextChanged.connect(self._on_behavior_mode_changed)
        self.reward_description.textChanged.connect(self._on_widget_changed)
        
        self.video_mode.currentTextChanged.connect(self._on_video_input_changed)
        self.video_loop.stateChanged.connect(self._on_widget_changed)
        self.video_fps.valueChanged.connect(self._on_widget_changed)
        self.video_path.textChanged.connect(self._on_widget_changed)

        lineedits = [
            self.reward_keys,
            self.reward_command,
            self.reward_url,
            self.reward_bearer_token,
            self.reward_headers,
            self.reward_payload,
            self.subject_label,
            self.object_label,
            self.target_zone_label,
            self.action_label
        ]

        for widget in lineedits:
            widget.textChanged.connect(self._on_widget_changed)

        self.start_pause_button.clicked.connect(self._on_start_pause_clicked)
        self.draw_capture_button.clicked.connect(self._on_draw_capture_region_clicked)
        self.draw_trigger_button.clicked.connect(self._on_draw_trigger_roi_clicked)
        self.save_button.clicked.connect(self.save_config)
        self.reload_button.clicked.connect(self.reload_config)
        self.reset_button.clicked.connect(self.reset_defaults)
        self.manual_capture_button.clicked.connect(self.manual_capture_requested.emit)
        self.exit_button.clicked.connect(self._on_exit_clicked)

    # ================================
    # SMALL HELPERS
    # ================================

    def _apply_responsive_window_size(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()

        if not screen:
            return

        geometry = screen.availableGeometry()

        panel_width = min(360, max(320, int(geometry.width() * 0.18)))
        panel_height = geometry.height()

        self.resize(panel_width, panel_height)
        self.setMinimumWidth(310)
        self.setMaximumWidth(380)

        self._pin_to_screen_right_edge()
        QTimer.singleShot(0, self._pin_to_screen_right_edge)
        QTimer.singleShot(100, self._pin_to_screen_right_edge)

    def _pin_to_screen_right_edge(self):
        screen = self.screen() or QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()

        if not screen:
            return

        geometry = screen.availableGeometry()
        frame = self.frameGeometry()

        frame_width = frame.width() if frame.width() > 0 else self.width()
        frame_height = frame.height() if frame.height() > 0 else self.height()

        target_frame_x = geometry.x() + geometry.width() - frame_width
        target_frame_y = geometry.y()

        frame_offset_x = self.pos().x() - frame.x()
        frame_offset_y = self.pos().y() - frame.y()

        self.move(
            target_frame_x + frame_offset_x,
            target_frame_y + frame_offset_y
        )

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._pin_to_screen_right_edge)
        QTimer.singleShot(100, self._pin_to_screen_right_edge)
        QTimer.singleShot(300, self._pin_to_screen_right_edge)

    def _capture_click_sequence_position(self, x_spin, y_spin):
        dialog = MousePositionCaptureDialog(self)

        if dialog.exec() == QDialog.Accepted and dialog.captured_position:
            x, y = dialog.captured_position
            x_spin.setValue(x)
            y_spin.setValue(y)
            self._on_widget_changed()
            
    def _clear_click_sequence_rows(self):
        while self.reward_click_sequence_layout.count():
            item = self.reward_click_sequence_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.reward_click_sequence_widgets = []

    def _rebuild_click_sequence_rows(self, sequence):
        self._rebuilding_click_sequence = True

        self._clear_click_sequence_rows()

        for index, step in enumerate(sequence):
            widgets = self._make_click_sequence_step_row(index, step)
            self.reward_click_sequence_widgets.append(widgets)
            self.reward_click_sequence_layout.addWidget(widgets["row"])

        self._rebuilding_click_sequence = False

    def _get_click_sequence_from_widgets(self):
        sequence = []

        for widgets in self.reward_click_sequence_widgets:
            sequence.append({
                "x": widgets["x"].value(),
                "y": widgets["y"].value(),
                "hold_duration": widgets["hold_duration"].value() / 1000.0,
                "delay_after": widgets["delay_after"].value() / 1000.0,
                "move_duration": widgets["move_duration"].value() / 1000.0
            })

        return sequence

    def _legacy_click_sequence_from_config(self, reward_cfg):
        clicks = int(reward_cfg.get("clicks", 1))
        clicks = max(0, min(99, clicks))

        x = int(reward_cfg.get("x", 735))
        y = int(reward_cfg.get("y", 586))
        delay_after = float(reward_cfg.get("interval", 0.1))
        move_duration = float(reward_cfg.get("move_duration", 0.0))

        return [
            {
                "x": x,
                "y": y,
                "hold_duration": 0.0,
                "delay_after": delay_after,
                "move_duration": move_duration
            }
            for _ in range(clicks)
        ]

    def _click_sequence_from_config(self, reward_cfg):
        sequence = reward_cfg.get("click_sequence")

        if isinstance(sequence, list):
            normalized_sequence = []

            for step in sequence:
                if not isinstance(step, dict):
                    continue

                normalized_sequence.append({
                    "x": int(step.get("x", reward_cfg.get("x", 735))),
                    "y": int(step.get("y", reward_cfg.get("y", 586))),
                    "hold_duration": float(step.get("hold_duration", 0.0)),
                    "delay_after": float(step.get("delay_after", reward_cfg.get("interval", 0.1))),
                    "move_duration": float(step.get("move_duration", reward_cfg.get("move_duration", 0.0)))
                })

            return normalized_sequence[:99]

        return self._legacy_click_sequence_from_config(reward_cfg)

    def _load_click_sequence_into_widgets(self, reward_cfg):
        sequence = self._click_sequence_from_config(reward_cfg)

        self._rebuilding_click_sequence = True
        self.reward_clicks.setValue(len(sequence))
        self._rebuilding_click_sequence = False

        self._rebuild_click_sequence_rows(sequence)

    def _on_reward_click_count_changed(self):
        if self._rebuilding_click_sequence:
            return

        existing_sequence = self._get_click_sequence_from_widgets()
        target_count = self.reward_clicks.value()

        if existing_sequence:
            default_step = existing_sequence[-1].copy()
        else:
            default_step = {
                "x": self.reward_x.value(),
                "y": self.reward_y.value(),
                "hold_duration": 0.0,
                "delay_after": self.reward_interval_ms.value() / 1000.0,
                "move_duration": self.reward_move_duration_ms.value() / 1000.0
            }

        while len(existing_sequence) < target_count:
            existing_sequence.append(default_step.copy())

        if len(existing_sequence) > target_count:
            existing_sequence = existing_sequence[:target_count]

        self._rebuild_click_sequence_rows(existing_sequence)
        self._on_widget_changed()

    def _parse_keys(self, text):
        return [part.strip() for part in text.split(",") if part.strip()]

    def _parse_json_text(self, text, fallback):
        value = text.strip()

        if not value:
            return fallback

        try:
            parsed = json.loads(value)
            return parsed
        except Exception:
            return fallback

    def _line_value(self, widget, fallback):
        value = widget.text().strip()
        return value if value else fallback

    def _on_widget_changed(self):
        self.config = self.get_current_config()
        self.status_label.setText("Unsaved changes")
        self.emit_config()

    def _automation_accessibility_required(self):
        return self.reward_mode.currentText().strip().lower() in {
            "mouse_click",
            "keyboard_shortcut",
        }

    def _automation_accessibility_ready(self):
        return accessibility_trusted()

    def _show_accessibility_required_dialog(self):
        request_accessibility_trust(prompt=True)

        message = QMessageBox(self)
        message.setWindowTitle("Accessibility Permission Required")
        message.setIcon(QMessageBox.Warning)
        message.setText(
            "This reward action requires macOS Accessibility permission."
        )
        message.setInformativeText(
            "BirdBros can detect events, but macOS will block automated "
            "mouse clicks and keyboard shortcuts until Accessibility is enabled.\n\n"
            "Open Accessibility Settings, add or enable BirdBros Recycle Co, "
            "then quit and reopen BirdBros.\n\n"
            "If you are running from source, enable Terminal instead."
        )

        open_button = message.addButton(
            "Open Accessibility Settings",
            QMessageBox.AcceptRole
        )
        message.addButton("Cancel", QMessageBox.RejectRole)

        message.exec()

        if message.clickedButton() == open_button:
            open_accessibility_settings()

        self.status_label.setText("Accessibility required for mouse_click")

    def _on_start_pause_clicked(self):
        starting_detection = self.detection_paused

        if (
            starting_detection
            and self._automation_accessibility_required()
            and not self._automation_accessibility_ready()
        ):
            self.detection_paused = True
            self.start_pause_button.setText("Start Detection")
            self._show_accessibility_required_dialog()
            return

        self.detection_paused = not self.detection_paused

        if self.detection_paused:
            self.start_pause_button.setText("Start Detection")
            self.status_label.setText("Detection paused")
        else:
            self.start_pause_button.setText("Pause Detection")
            self.status_label.setText("Detection running")

        self.detection_paused_changed.emit(self.detection_paused)

    def _current_capture_region(self):
        return CaptureRegion(
            left=self.capture_left.value(),
            top=self.capture_top.value(),
            width=self.capture_width.value(),
            height=self.capture_height.value(),
        )

    def _on_draw_capture_region_clicked(self):
        dialog = RegionDragCaptureDialog(
            title="Draw Capture Region",
            instructions=(
                "Draw the full screen area BirdBros should analyze.\n"
                "This sets Capture Region: Left, Top, Width, and Height."
            ),
            parent=self
        )

        if dialog.exec() != QDialog.Accepted or dialog.selected_rect is None:
            return

        capture_region = CaptureRegion.from_screen_tuple(dialog.selected_rect)

        self._apply_capture_region_to_fields(capture_region)

        self.status_label.setText("Capture region updated")
        self._on_widget_changed()

    def _on_draw_trigger_roi_clicked(self):
        capture_region = self._current_capture_region()

        if capture_region.width <= 0 or capture_region.height <= 0:
            QMessageBox.warning(
                self,
                "Capture Region Required",
                "Set a valid Capture Region before drawing the Trigger ROI."
            )
            return

        dialog = RegionDragCaptureDialog(
            title="Draw Trigger ROI",
            instructions=(
                "Draw the trigger/drop zone inside the current Capture Region.\n"
                "This sets Trigger ROI: X, Y, W, and H relative to the Capture Region."
            ),
            parent=self
        )

        if dialog.exec() != QDialog.Accepted or dialog.selected_rect is None:
            return

        trigger_roi = ROI.trigger_object_from_screen_tuple(
            rect_tuple=dialog.selected_rect,
            capture_region=capture_region,
        )

        self._apply_object_roi_to_fields(trigger_roi)

        self.status_label.setText("Trigger ROI updated")
        self._on_widget_changed()

    def apply_live_region_edit(self, capture_region=None, object_roi=None, subject_roi=None):
        widgets = [
            self.capture_left,
            self.capture_top,
            self.capture_width,
            self.capture_height,
            self.subject_x,
            self.subject_y,
            self.subject_w,
            self.subject_h,
            self.object_x,
            self.object_y,
            self.object_w,
            self.object_h,
        ]

        previous_signal_states = {}

        for widget in widgets:
            previous_signal_states[widget] = widget.blockSignals(True)

        try:
            if capture_region is not None:
                self._apply_capture_region_to_fields(capture_region)

            if subject_roi is not None:
                self._apply_subject_roi_to_fields(subject_roi)

            if object_roi is not None:
                self._apply_object_roi_to_fields(object_roi)

        finally:
            for widget in widgets:
                widget.blockSignals(previous_signal_states[widget])

        self.status_label.setText("Live region edit applied")
        self._on_widget_changed()

    def _on_exit_clicked(self):
        self.exit_requested.emit()

    def closeEvent(self, event):
        self.exit_requested.emit()
        event.accept()

    def emit_config(self):
        self.config_changed.emit(self.get_current_config())

    # ================================
    # DYNAMIC REWARD ACTION UI
    # ================================

    def _on_reward_action_changed(self):
        action_type = self.reward_mode.currentText()
        visibility = self._apply_reward_action_visibility(action_type)

        self._on_widget_changed()

        if (
            (
                visibility["mouse_visible"]
                or visibility["keyboard_visible"]
            )
            and not self._automation_accessibility_ready()
        ):
            self.status_label.setText("Accessibility required for automated rewards")
        
    # ================================
    # DYNAMIC VIDEO INPUT UI
    # ================================
    
    def _on_behavior_mode_changed(self):
        self._apply_behavior_mode_visibility(
            self.behavior_mode.currentText()
        )
        self._on_widget_changed()

    def _on_video_input_changed(self):
        self._apply_video_input_visibility(
            self.video_mode.currentText()
        )
        self._on_widget_changed()

    # ================================
    # UI → CONFIG SYNC
    # ================================

    def get_current_config(self):
        capture_region = self._current_capture_region()

        subject_roi = ROI.subject(
            x=self.subject_x.value(),
            y=self.subject_y.value(),
            width=self.subject_w.value(),
            height=self.subject_h.value(),
        )

        object_roi = ROI.trigger_object(
            x=self.object_x.value(),
            y=self.object_y.value(),
            width=self.object_w.value(),
            height=self.object_h.value(),
        )

        default_task = DEFAULT_CONFIG["task_labels"]

        click_sequence = self._get_click_sequence_from_widgets()

        if click_sequence:
            first_click = click_sequence[0]
        else:
            first_click = {
                "x": self.reward_x.value(),
                "y": self.reward_y.value(),
                "delay_after": self.reward_interval_ms.value() / 1000.0,
                "move_duration": self.reward_move_duration_ms.value() / 1000.0
            }

        return {
            "capture_region": capture_region.to_config(),
            "video_input": {
                "mode": self.video_mode.currentText(),
                "video_path": self.video_path.text().strip(),
                "loop_video": self.video_loop.isChecked(),
                "fps": self.video_fps.value()
            },
            "subject_roi": subject_roi.to_percent_config(capture_region),
            "object_roi": object_roi.to_percent_config(capture_region),
            "motion": {
                "min_area": self.motion_min_area.value()
            },
            "display": {
                "show_overlay": self.show_overlay.isChecked(),
                "show_grid": self.show_grid.isChecked(),
                "show_coords": self.show_coords.isChecked(),
                "show_capture_border": self.show_capture_border.isChecked(),
                "show_labels": self.show_labels.isChecked()
            },
            "task_labels": {
                "subject_label": self._line_value(self.subject_label, default_task["subject_label"]),
                "object_label": self._line_value(self.object_label, default_task["object_label"]),
                "target_zone_label": self._line_value(self.target_zone_label, default_task["target_zone_label"]),
                "action_label": self._line_value(self.action_label, default_task["action_label"])
            },

            "behavior_mode": self.behavior_mode.currentText(),

            "reward_description": self.reward_description.text().strip(),

            "reward_action": {
                "mode": self.reward_mode.currentText(),

                # Legacy/default fields preserved for compatibility.
                "x": first_click["x"],
                "y": first_click["y"],
                "clicks": self.reward_clicks.value(),
                "interval": first_click.get("delay_after", 0.0),
                "move_duration": first_click.get("move_duration", 0.0),

                # New executable click choreography.
                "click_sequence": click_sequence,

                "keys": self._parse_keys(self.reward_keys.text()),
                "command": self.reward_command.text().strip(),
                "url": self.reward_url.text().strip(),
                "method": self.reward_method.currentText(),
                "timeout": self.reward_timeout.value(),
                "bearer_token": self.reward_bearer_token.text().strip(),
                "headers": self._parse_json_text(self.reward_headers.text(), {}),
                "payload": self._parse_json_text(self.reward_payload.text(), {})
            },
            "no_reward_action": self.config.get("no_reward_action", {"mode": "debug_popup"})
        }

    # ================================
    # CONFIG → UI SYNC
    # ================================

    def _load_config_into_widgets(self):
        cfg = self.config

        capture_region = CaptureRegion.from_config(cfg)
        self._apply_capture_region_to_fields(capture_region)
        
        video_cfg = cfg.get("video_input", DEFAULT_CONFIG["video_input"])

        self.video_mode.setCurrentText(video_cfg.get("mode", "screen_capture"))
        self.video_path.setText(video_cfg.get("video_path", ""))
        self.video_loop.setChecked(video_cfg.get("loop_video", True))
        self.video_fps.setValue(video_cfg.get("fps", 30))

        subject_roi = ROI.subject_from_percent_config(
            config=cfg,
            capture_region=capture_region,
        )

        object_roi = ROI.trigger_object_from_percent_config(
            config=cfg,
            capture_region=capture_region,
        )

        self._apply_subject_roi_to_fields(subject_roi)
        self._apply_object_roi_to_fields(object_roi)

        self.motion_min_area.setValue(max(100, min(50000, cfg["motion"]["min_area"])))
        
        display = cfg.get("display", {})
        self.show_overlay.setChecked(display.get("show_overlay", True))
        self.show_grid.setChecked(display.get("show_grid", True))
        self.show_coords.setChecked(display.get("show_coords", True))
        self.show_capture_border.setChecked(display.get("show_capture_border", True))
        self.show_labels.setChecked(display.get("show_labels", True))

        task = cfg.get("task_labels", DEFAULT_CONFIG["task_labels"])
        self.behavior_mode.setCurrentText(
            cfg.get("behavior_mode", "simple")
        )

        self.reward_description.setText(
            cfg.get("reward_description", "")
        )
        self.reward_description.setCursorPosition(0)

        self._on_behavior_mode_changed()

        self.subject_label.setText(task.get("subject_label", DEFAULT_CONFIG["task_labels"]["subject_label"]))
        self.object_label.setText(task.get("object_label", DEFAULT_CONFIG["task_labels"]["object_label"]))
        self.target_zone_label.setText(task.get("target_zone_label", DEFAULT_CONFIG["task_labels"]["target_zone_label"]))
        self.action_label.setText(task.get("action_label", DEFAULT_CONFIG["task_labels"]["action_label"]))

        reward_cfg = cfg.get("reward_action", {})
        reward_mode = reward_cfg.get("mode", "overlay_status")

        if reward_mode == "debug_popup":
            reward_mode = "overlay_status"
        
        self.reward_mode.setCurrentText(reward_mode)

        self._load_click_sequence_into_widgets(reward_cfg)

        click_sequence = self._get_click_sequence_from_widgets()

        if click_sequence:
            first_click = click_sequence[0]
            self.reward_x.setValue(first_click.get("x", 735))
            self.reward_y.setValue(first_click.get("y", 586))
            self.reward_interval_ms.setValue(int(first_click.get("delay_after", 0.1) * 1000))
            self.reward_move_duration_ms.setValue(int(first_click.get("move_duration", 0.0) * 1000))
        else:
            self.reward_x.setValue(reward_cfg.get("x", 735))
            self.reward_y.setValue(reward_cfg.get("y", 586))
            self.reward_interval_ms.setValue(int(reward_cfg.get("interval", 0.1) * 1000))
            self.reward_move_duration_ms.setValue(int(reward_cfg.get("move_duration", 0.0) * 1000))

        self.reward_keys.setText(",".join(reward_cfg.get("keys", ["command", "space"])))
        self.reward_command.setText(reward_cfg.get("command", ""))
        self.reward_url.setText(reward_cfg.get("url", ""))
        self.reward_method.setCurrentText(reward_cfg.get("method", "POST"))
        self.reward_timeout.setValue(int(reward_cfg.get("timeout", 5)))
        self.reward_bearer_token.setText(reward_cfg.get("bearer_token", ""))
        self.reward_headers.setText(json.dumps(reward_cfg.get("headers", {})))
        self.reward_payload.setText(json.dumps(reward_cfg.get("payload", {})))

        self.status_label.setText("Config loaded")
        self._on_reward_action_changed()
        self._on_video_input_changed()

    # ================================
    # CONFIG FILE ACTIONS
    # ================================

    def save_config(self):
        self.config = self.get_current_config()

        try:
            save_config(self.config, self.config_path)
            self.status_label.setText(f"Saved: {self.config_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))
            self.status_label.setText("Save failed")

    def reload_config(self):
        self.config = load_config(self.config_path)
        self._load_config_into_widgets()
        self.emit_config()

    def reset_defaults(self):
        self.config = json.loads(json.dumps(DEFAULT_CONFIG))
        self._load_config_into_widgets()
        self.emit_config()
        self.status_label.setText("Reset to defaults")
        
    def mousePressEvent(self, event):
        self.permanent_surface_clicked.emit()
        super().mousePressEvent(event)


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
config_manager → control_panel → main.py

KEY BEHAVIOR:
- ROI controls display pixels but store percentages
- Task-label controls feed configurable OpenAI prompt variables
- Reward controls remain runtime editable
- Reward action fields appear only when relevant to the selected reward mode
"""
