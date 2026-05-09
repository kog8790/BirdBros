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
Allow open-source users to tune both system geometry and AI task wording without code edits. """

import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
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

    def __init__(self, config_path="birdbros_config.json"):
        super().__init__()

        self.config_path = config_path
        self.config = load_config(self.config_path)

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

        subject_group = QGroupBox("Subject ROI")
        subject_form = QFormLayout()

        self.subject_x = self._make_spinbox(0, 10000)
        self.subject_y = self._make_spinbox(0, 10000)
        self.subject_w = self._make_spinbox(1, 10000)
        self.subject_h = self._make_spinbox(1, 10000)

        subject_form.addRow("X", self.subject_x)
        subject_form.addRow("Y", self.subject_y)
        subject_form.addRow("W", self.subject_w)
        subject_form.addRow("H", self.subject_h)
        subject_group.setLayout(subject_form)

        object_group = QGroupBox("Object ROI")
        object_form = QFormLayout()

        self.object_x = self._make_spinbox(0, 10000)
        self.object_y = self._make_spinbox(0, 10000)
        self.object_w = self._make_spinbox(1, 10000)
        self.object_h = self._make_spinbox(1, 10000)

        object_form.addRow("X", self.object_x)
        object_form.addRow("Y", self.object_y)
        object_form.addRow("W", self.object_w)
        object_form.addRow("H", self.object_h)
        object_group.setLayout(object_form)

        motion_group = QGroupBox("Motion")
        motion_form = QFormLayout()

        self.motion_min_area = self._make_spinbox(1, 1000000)
        motion_form.addRow("Min Area", self.motion_min_area)
        motion_group.setLayout(motion_form)

        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout()

        self.show_overlay = QCheckBox("Show Overlay")
        self.show_grid = QCheckBox("Show Grid")
        self.show_coords = QCheckBox("Show Coordinates")
        self.show_capture_border = QCheckBox("Show Capture Border")
        self.show_labels = QCheckBox("Show Labels")

        display_layout.addWidget(self.show_overlay)
        display_layout.addWidget(self.show_grid)
        display_layout.addWidget(self.show_coords)
        display_layout.addWidget(self.show_capture_border)
        display_layout.addWidget(self.show_labels)
        display_group.setLayout(display_layout)

        task_group = QGroupBox("AI Task Labels")
        task_form = QFormLayout()

        self.subject_label = QLineEdit()
        self.object_label = QLineEdit()
        self.target_zone_label = QLineEdit()
        self.action_label = QLineEdit()

        self.subject_label.setPlaceholderText("non-human animal")
        self.object_label.setPlaceholderText("man-made litter or trash")
        self.target_zone_label.setPlaceholderText("trash receptacle")
        self.action_label.setPlaceholderText("depositing")

        task_form.addRow("Subject", self.subject_label)
        task_form.addRow("Object", self.object_label)
        task_form.addRow("Target Zone", self.target_zone_label)
        task_form.addRow("Action", self.action_label)
        task_group.setLayout(task_form)

        reward_group = QGroupBox("Reward Action")
        reward_form = QFormLayout()

        self.reward_mode = QComboBox()
        self.reward_mode.addItems(["debug_popup", "mouse_click", "keyboard_shortcut", "webhook", "shell_command"])

        self.reward_x = self._make_spinbox(0, 10000)
        self.reward_y = self._make_spinbox(0, 10000)
        self.reward_clicks = self._make_spinbox(1, 20)
        self.reward_interval_ms = self._make_spinbox(0, 10000)
        self.reward_move_duration_ms = self._make_spinbox(0, 10000)

        self.reward_keys = QLineEdit()
        self.reward_keys.setPlaceholderText("command,space")

        self.reward_command = QLineEdit()
        self.reward_command.setPlaceholderText("python3 my_script.py")

        self.reward_url = QLineEdit()
        self.reward_url.setPlaceholderText("https://example.com/webhook")

        self.reward_method = QComboBox()
        self.reward_method.addItems(["POST", "GET"])

        self.reward_timeout = self._make_spinbox(1, 300)

        reward_form.addRow("Mode", self.reward_mode)
        reward_form.addRow("Mouse X", self.reward_x)
        reward_form.addRow("Mouse Y", self.reward_y)
        reward_form.addRow("Mouse Clicks", self.reward_clicks)
        reward_form.addRow("Click Interval (ms)", self.reward_interval_ms)
        reward_form.addRow("Move Duration (ms)", self.reward_move_duration_ms)
        reward_form.addRow("Shortcut Keys", self.reward_keys)
        reward_form.addRow("Shell Command", self.reward_command)
        reward_form.addRow("Webhook URL", self.reward_url)
        reward_form.addRow("Webhook Method", self.reward_method)
        reward_form.addRow("Webhook Timeout (s)", self.reward_timeout)
        reward_group.setLayout(reward_form)

        button_row = QHBoxLayout()

        self.save_button = QPushButton("Save Config")
        self.reload_button = QPushButton("Reload Config")
        self.reset_button = QPushButton("Reset Defaults")
        self.manual_capture_button = QPushButton("Manual ROI Capture")
        self.exit_button = QPushButton("Exit")

        button_row.addWidget(self.save_button)
        button_row.addWidget(self.reload_button)
        button_row.addWidget(self.reset_button)
        button_row.addWidget(self.manual_capture_button)
        button_row.addWidget(self.exit_button)

        self.status_label = QLabel("Ready")

        main_layout.addWidget(capture_group)
        main_layout.addWidget(subject_group)
        main_layout.addWidget(object_group)
        main_layout.addWidget(motion_group)
        main_layout.addWidget(display_group)
        main_layout.addWidget(task_group)
        main_layout.addWidget(reward_group)
        main_layout.addLayout(button_row)
        main_layout.addWidget(self.status_label)

        content_widget = QWidget()
        content_widget.setLayout(main_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)

        outer_layout = QVBoxLayout()
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

        combos = [self.reward_mode, self.reward_method]
        for widget in combos:
            widget.currentIndexChanged.connect(self._on_widget_changed)

        lineedits = [
            self.reward_keys,
            self.reward_command,
            self.reward_url,
            self.subject_label,
            self.object_label,
            self.target_zone_label,
            self.action_label
        ]

        for widget in lineedits:
            widget.textChanged.connect(self._on_widget_changed)

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

        panel_width = int(geometry.width() * 0.32)
        panel_height = int(geometry.height() * 0.82)

        self.resize(panel_width, panel_height)
        self.setMinimumWidth(int(geometry.width() * 0.24))

    def _make_spinbox(self, min_value, max_value):
        spin = QSpinBox()
        spin.setRange(min_value, max_value)
        spin.setSingleStep(1)
        return spin

    def _parse_keys(self, text):
        return [part.strip() for part in text.split(",") if part.strip()]

    def _line_value(self, widget, fallback):
        value = widget.text().strip()
        return value if value else fallback

    def _on_widget_changed(self):
        self.config = self.get_current_config()
        self.status_label.setText("Unsaved changes")
        self.emit_config()

    def _on_exit_clicked(self):
        self.exit_requested.emit()

    def emit_config(self):
        self.config_changed.emit(self.get_current_config())

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
                "timeout": self.reward_timeout.value()
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

        self.motion_min_area.setValue(cfg["motion"]["min_area"])

        display = cfg.get("display", {})
        self.show_overlay.setChecked(display.get("show_overlay", True))
        self.show_grid.setChecked(display.get("show_grid", True))
        self.show_coords.setChecked(display.get("show_coords", True))
        self.show_capture_border.setChecked(display.get("show_capture_border", True))
        self.show_labels.setChecked(display.get("show_labels", True))

        task = cfg.get("task_labels", DEFAULT_CONFIG["task_labels"])
        self.subject_label.setText(task.get("subject_label", DEFAULT_CONFIG["task_labels"]["subject_label"]))
        self.object_label.setText(task.get("object_label", DEFAULT_CONFIG["task_labels"]["object_label"]))
        self.target_zone_label.setText(task.get("target_zone_label", DEFAULT_CONFIG["task_labels"]["target_zone_label"]))
        self.action_label.setText(task.get("action_label", DEFAULT_CONFIG["task_labels"]["action_label"]))

        reward_cfg = cfg.get("reward_action", {})
        self.reward_mode.setCurrentText(reward_cfg.get("mode", "debug_popup"))
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

        self.status_label.setText("Config loaded")

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
- Reward controls remain runtime editable """
