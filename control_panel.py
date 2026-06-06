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
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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
    QScrollArea
)

from config_manager import DEFAULT_CONFIG, load_config, save_config


class control_panel(QWidget):
    config_changed = Signal(dict)
    exit_requested = Signal()
    manual_capture_requested = Signal()
    detection_paused_changed = Signal(bool)

    def __init__(self, config_path="birdbros_config.json"):
        super().__init__()

        self.config_path = config_path
        self.config = load_config(self.config_path)
        self.detection_paused = True

        self.setWindowTitle("Bird Bros Control Panel")
        self._apply_responsive_window_size()
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        self._build_ui()
        self._load_config_into_widgets()
        self._connect_signals()
        self.emit_config()

    # ================================
    # UI CONSTRUCTION
    # ================================

    def _build_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        main_layout.setSpacing(14)

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
        display_layout.addWidget(self.show_coords, 0, 2)

        display_layout.addWidget(self.show_capture_border, 1, 0)
        display_layout.addWidget(self.show_labels, 1, 1)
        display_group.setLayout(display_layout)

        task_group = QGroupBox("AI Task Labels")
        task_form = QFormLayout()

        self.behavior_mode = QComboBox()
        self.behavior_mode.addItems(["simple", "advanced"])

        self.reward_description = QLineEdit()
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

        task_form.addRow("Behavior Mode", self.behavior_mode)

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
        self.reward_x = self._make_spinbox(0, 10000)
        self.reward_y = self._make_spinbox(0, 10000)
        self.reward_clicks = self._make_spinbox(1, 20)
        self.reward_interval_ms = self._make_spinbox(0, 10000)
        self.reward_move_duration_ms = self._make_spinbox(0, 10000)

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
        reward_layout.addWidget(self.reward_keys_row)
        reward_layout.addWidget(self.reward_command_row)
        reward_layout.addWidget(self.reward_url_row)
        reward_layout.addWidget(self.reward_method_row)
        reward_layout.addWidget(self.reward_timeout_row)
        reward_layout.addWidget(self.reward_bearer_row)
        reward_layout.addWidget(self.reward_headers_row)
        reward_layout.addWidget(self.reward_payload_row)

        reward_group.setLayout(reward_layout)

        button_grid = QGridLayout()
        button_grid.setSpacing(10)

        self.start_pause_button = QPushButton("Start Detection")
        self.save_button = QPushButton("Save Config")
        self.reload_button = QPushButton("Reload Config")
        self.reset_button = QPushButton("Reset Defaults")
        self.manual_capture_button = QPushButton("Manual ROI Capture")
        self.exit_button = QPushButton("Exit")

        button_grid.addWidget(self.start_pause_button, 0, 0)
        button_grid.addWidget(self.save_button, 0, 1)
        button_grid.addWidget(self.reload_button, 0, 2)

        button_grid.addWidget(self.reset_button, 1, 0)
        button_grid.addWidget(self.manual_capture_button, 1, 1)
        button_grid.addWidget(self.exit_button, 1, 2)

        self.status_label = QLabel("Ready")

        main_layout.addWidget(capture_group)
        main_layout.addWidget(video_group)
        main_layout.addWidget(self.subject_group)
        main_layout.addWidget(self.object_group)
        main_layout.addWidget(motion_group)
        main_layout.addWidget(display_group)
        main_layout.addWidget(task_group)
        main_layout.addWidget(reward_group)
        main_layout.addLayout(button_grid)
        main_layout.addWidget(self.status_label)

        content_widget = QWidget()
        content_widget.setLayout(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        outer_layout.setContentsMargins(18, 18, 18, 18)
        outer_layout.setSpacing(14)
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
            self.reward_x, self.reward_y, self.reward_clicks,
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
        self.save_button.clicked.connect(self.save_config)
        self.reload_button.clicked.connect(self.reload_config)
        self.reset_button.clicked.connect(self.reset_defaults)
        self.manual_capture_button.clicked.connect(self.manual_capture_requested.emit)
        self.exit_button.clicked.connect(self._on_exit_clicked)

    # ================================
    # SMALL HELPERS
    # ================================

    def _apply_responsive_window_size(self):
        screen = QApplication.primaryScreen()

        if not screen:
            return

        geometry = screen.availableGeometry()

        panel_width = int(geometry.width() * 0.20)
        panel_height = geometry.height()

        self.resize(panel_width, panel_height)
        self.setMinimumWidth(int(geometry.width() * 0.14))

    def _make_spinbox(self, min_value, max_value):
        spin = QSpinBox()
        spin.setRange(min_value, max_value)
        spin.setSingleStep(1)
        return spin

    def _make_reward_row(self, label_text, widget):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)

        label = QLabel(label_text)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        row_layout.addWidget(label, 1)
        row_layout.addWidget(widget, 1)

        return row

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
        
    def _on_start_pause_clicked(self):
        self.detection_paused = not self.detection_paused

        if self.detection_paused:
            self.start_pause_button.setText("Start Detection")
            self.status_label.setText("Detection paused")
        else:
            self.start_pause_button.setText("Pause Detection")
            self.status_label.setText("Detection running")

        self.detection_paused_changed.emit(self.detection_paused)

    def _on_exit_clicked(self):
        self.exit_requested.emit()

    def emit_config(self):
        self.config_changed.emit(self.get_current_config())

    # ================================
    # DYNAMIC REWARD ACTION UI
    # ================================

    def _on_reward_action_changed(self):
        action_type = self.reward_mode.currentText()

        mouse_visible = action_type == "mouse_click"
        keyboard_visible = action_type == "keyboard_shortcut"
        command_visible = action_type == "shell_command"
        webhook_visible = action_type == "webhook"

        self.reward_x_row.setVisible(mouse_visible)
        self.reward_y_row.setVisible(mouse_visible)
        self.reward_clicks_row.setVisible(mouse_visible)
        self.reward_interval_row.setVisible(mouse_visible)
        self.reward_move_duration_row.setVisible(mouse_visible)

        self.reward_keys_row.setVisible(keyboard_visible)

        self.reward_command_row.setVisible(command_visible)

        self.reward_url_row.setVisible(webhook_visible)
        self.reward_method_row.setVisible(webhook_visible)
        self.reward_timeout_row.setVisible(webhook_visible)
        self.reward_bearer_row.setVisible(webhook_visible)
        self.reward_headers_row.setVisible(webhook_visible)
        self.reward_payload_row.setVisible(webhook_visible)

        self._on_widget_changed()
        
    # ================================
    # DYNAMIC VIDEO INPUT UI
    # ================================
    
    def _on_behavior_mode_changed(self):
        advanced_visible = (
            self.behavior_mode.currentText() == "advanced"
        )

        self.subject_label_widget.setVisible(advanced_visible)
        self.subject_label.setVisible(advanced_visible)

        self.object_label_widget.setVisible(advanced_visible)
        self.object_label.setVisible(advanced_visible)

        self.target_zone_label_widget.setVisible(advanced_visible)
        self.target_zone_label.setVisible(advanced_visible)

        self.action_label_widget.setVisible(advanced_visible)
        self.action_label.setVisible(advanced_visible)

        self.subject_group.setVisible(advanced_visible)

        if advanced_visible:
            self.object_group.setTitle("Object ROI")
        else:
            self.object_group.setTitle("Trigger ROI")

        self._on_widget_changed()

    def _on_video_input_changed(self):
        input_mode = self.video_mode.currentText()

        video_file_visible = input_mode == "video_file"

        self.video_path_row.setVisible(video_file_visible)
        self.video_loop_row.setVisible(video_file_visible)

        self._on_widget_changed()

    # ================================
    # UI → CONFIG SYNC
    # ================================

    def get_current_config(self):
        def px_to_pct(value_px, total):
            return value_px / total if total else 0

        capture_width = self.capture_width.value()
        capture_height = self.capture_height.value()

        default_task = DEFAULT_CONFIG["task_labels"]

        return {
            "capture_region": {
                "left": self.capture_left.value(),
                "top": self.capture_top.value(),
                "width": capture_width,
                "height": capture_height
            },
            "video_input": {
                "mode": self.video_mode.currentText(),
                "video_path": self.video_path.text().strip(),
                "loop_video": self.video_loop.isChecked(),
                "fps": self.video_fps.value()
            },
            "subject_roi": {
                "x_pct": px_to_pct(self.subject_x.value(), capture_width),
                "y_pct": px_to_pct(self.subject_y.value(), capture_height),
                "w_pct": px_to_pct(self.subject_w.value(), capture_width),
                "h_pct": px_to_pct(self.subject_h.value(), capture_height)
            },
            "object_roi": {
                "x_pct": px_to_pct(self.object_x.value(), capture_width),
                "y_pct": px_to_pct(self.object_y.value(), capture_height),
                "w_pct": px_to_pct(self.object_w.value(), capture_width),
                "h_pct": px_to_pct(self.object_h.value(), capture_height)
            },
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
                "x": self.reward_x.value(),
                "y": self.reward_y.value(),
                "clicks": self.reward_clicks.value(),
                "interval": self.reward_interval_ms.value() / 1000.0,
                "move_duration": self.reward_move_duration_ms.value() / 1000.0,
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

        self.capture_left.setValue(cfg["capture_region"]["left"])
        self.capture_top.setValue(cfg["capture_region"]["top"])
        self.capture_width.setValue(cfg["capture_region"]["width"])
        self.capture_height.setValue(cfg["capture_region"]["height"])
        
        video_cfg = cfg.get("video_input", DEFAULT_CONFIG["video_input"])

        self.video_mode.setCurrentText(video_cfg.get("mode", "screen_capture"))
        self.video_path.setText(video_cfg.get("video_path", ""))
        self.video_loop.setChecked(video_cfg.get("loop_video", True))
        self.video_fps.setValue(video_cfg.get("fps", 6))

        def pct_to_px(value_pct, total):
            return int(value_pct * total)

        region = cfg["capture_region"]

        self.subject_x.setValue(pct_to_px(cfg["subject_roi"]["x_pct"], region["width"]))
        self.subject_y.setValue(pct_to_px(cfg["subject_roi"]["y_pct"], region["height"]))
        self.subject_w.setValue(pct_to_px(cfg["subject_roi"]["w_pct"], region["width"]))
        self.subject_h.setValue(pct_to_px(cfg["subject_roi"]["h_pct"], region["height"]))

        self.object_x.setValue(pct_to_px(cfg["object_roi"]["x_pct"], region["width"]))
        self.object_y.setValue(pct_to_px(cfg["object_roi"]["y_pct"], region["height"]))
        self.object_w.setValue(pct_to_px(cfg["object_roi"]["w_pct"], region["width"]))
        self.object_h.setValue(pct_to_px(cfg["object_roi"]["h_pct"], region["height"]))

        self.motion_min_area.setValue(max(100, min(50000, cfg["motion"]["min_area"])))
        
        display = cfg.get("display", {})
        self.show_overlay.setChecked(display.get("show_overlay", True))
        self.show_grid.setChecked(display.get("show_grid", True))
        self.show_coords.setChecked(display.get("show_coords", True))
        self.show_capture_border.setChecked(display.get("show_capture_border", True))
        self.show_labels.setChecked(display.get("show_labels", True))

        task = cfg.get("task_labels", DEFAULT_CONFIG["task_labels"])
        self.behavior_mode.setCurrentText(
            cfg.get("behavior_mode", "advanced")
        )

        self.reward_description.setText(
            cfg.get("reward_description", "")
        )

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
        self.reward_x.setValue(reward_cfg.get("x", 735))
        self.reward_y.setValue(reward_cfg.get("y", 586))
        self.reward_clicks.setValue(reward_cfg.get("clicks", 3))
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


""" ### SEGMENT: SYSTEM CONTEXT ###
FLOW:
config_manager → control_panel → main.py

KEY BEHAVIOR:
- ROI controls display pixels but store percentages
- Task-label controls feed configurable OpenAI prompt variables
- Reward controls remain runtime editable
- Reward action fields appear only when relevant to the selected reward mode
"""
