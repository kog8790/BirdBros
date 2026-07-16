import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

class control_panel_ui:
    def _apply_visual_style(self):
        self.setStyleSheet(
            """
            QWidget#birdbros_control_panel {
                background-color: #101214;
                color: #ECE8DD;
                font-family: "SF Pro Display", "Helvetica Neue", Arial;
                font-size: 12px;
            }

            QWidget#sidebarHeader {
                background-color: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: 18px;
                min-height: 88px;
                max-height: 96px;
            }

            QWidget#headerTextStack {
                background-color: transparent;
            }

            QLabel#appIcon {
                color: #F8F3E7;
                font-size: 30px;
                background-color: transparent;
            }

            QLabel#appHeader {
                color: #F8F3E7;
                font-size: 16px;
                font-weight: 850;
                letter-spacing: 0.05px;
                background-color: transparent;
            }

            QLabel#headerSpacer {
                color: transparent;
                background-color: transparent;
                font-size: 1px;
            }

            QLabel#appDescriptorPrimary {
                color: #F1D99B;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 0.05px;
                background-color: transparent;
            }

            QLabel#appDescriptor {
                color: rgba(236, 232, 221, 150);
                font-size: 10px;
                font-weight: 650;
                background-color: transparent;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }

            QWidget#collapsibleSection {
                background-color: transparent;
                margin: 0px;
                padding: 0px;
            }

            QWidget#sectionHeaderCard {
                background-color: rgba(255, 255, 255, 13);
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: 14px;
            }

            QWidget#sectionHeaderCard:hover {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(180, 180, 172, 72);
            }

            QWidget#sectionHeaderCard[expanded="true"] {
                background-color: rgba(255, 255, 255, 16);
                border: 1px solid rgba(210, 207, 196, 90);
            }

            QLabel#sectionSideIcon {
                color: rgba(245, 238, 220, 190);
                background-color: rgba(255, 255, 255, 8);
                border: 1px solid rgba(210, 207, 196, 46);
                border-radius: 9px;
                font-size: 8px;
                font-weight: 850;
                letter-spacing: 0.6px;
            }

            QLabel#sectionHeaderTitle {
                color: #F5EEDC;
                background-color: transparent;
                font-size: 12px;
                font-weight: 850;
            }

            QGroupBox {
                background-color: rgba(255, 255, 255, 14);
                border: 1px solid rgba(255, 255, 255, 25);
                border-radius: 16px;
                margin-top: 8px;
                padding: 10px 8px 8px 8px;
                color: #F5EEDC;
                font-size: 12px;
                font-weight: 700;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                top: 1px;
                padding: 0 8px;
                color: #F1D99B;
                background-color: #101214;
                border-radius: 8px;
            }

            QGroupBox#capturePositionCard {
                background-color: #171B1D;
                border: 1px solid rgba(116, 215, 196, 150);
                border-radius: 18px;
                color: #F8F3E7;
            }

            QGroupBox#capturePositionCard::title {
                color: #F1D99B;
                background-color: #171B1D;
            }

            QLabel {
                color: #ECE8DD;
            }

            QLabel#fieldLabel {
                color: rgba(236, 232, 221, 165);
                font-size: 11px;
                font-weight: 650;
            }

            QLabel#clickSequenceTitle {
                color: #F5EEDC;
                font-size: 12px;
                font-weight: 800;
            }

            QWidget#clickSequenceStep {
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 12px;
            }

            QLabel#footerStatus {
                color: rgba(245, 238, 220, 180);
                background-color: rgba(255, 255, 255, 12);
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 12px;
                padding: 9px;
                font-size: 11px;
                font-weight: 650;
            }

            QLineEdit, QSpinBox, QComboBox {
                color: #F8F3E7;
                background-color: rgba(255, 255, 255, 22);
                border: 1px solid rgba(255, 255, 255, 34);
                border-radius: 10px;
                padding: 6px 7px;
                selection-background-color: #74D7C4;
                selection-color: #101214;
            }

            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #74D7C4;
                background-color: rgba(255, 255, 255, 31);
            }

            QComboBox QAbstractItemView {
                color: #F8F3E7;
                background-color: #202426;
                selection-background-color: #74D7C4;
                selection-color: #101214;
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 8px;
                outline: none;
                padding: 4px;
            }

            QComboBox QAbstractItemView::item {
                color: #F8F3E7;
                background-color: #202426;
                min-height: 26px;
                padding: 6px 10px;
                border-radius: 6px;
            }

            QComboBox QAbstractItemView::item:hover {
                color: #101214;
                background-color: #74D7C4;
            }

            QComboBox QAbstractItemView::item:selected {
                color: #101214;
                background-color: #74D7C4;
            }

            QComboBox QAbstractItemView::item:disabled {
                color: rgba(248, 243, 231, 95);
                background-color: #202426;
            }

            QComboBox::drop-down {
                border: none;
                width: 22px;
                background-color: transparent;
            }

            QCheckBox {
                color: rgba(245, 238, 220, 210);
                spacing: 7px;
                font-size: 11px;
                font-weight: 550;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 55);
                background-color: rgba(255, 255, 255, 18);
            }

            QCheckBox::indicator:checked {
                background-color: #74D7C4;
                border: 1px solid #74D7C4;
            }

            QPushButton {
                color: #F8F3E7;
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 32);
                border-radius: 13px;
                padding: 8px 8px;
                font-size: 11px;
                font-weight: 750;
            }

            QPushButton:hover {
                background-color: rgba(255, 255, 255, 32);
                border: 1px solid rgba(255, 255, 255, 55);
            }

            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 16);
            }

            QPushButton#primaryButton {
                color: #08110F;
                background-color: #74D7C4;
                border: 1px solid #9FE8DB;
                font-size: 12px;
                padding: 10px 8px;
            }

            QPushButton#primaryButton:hover {
                background-color: #91E4D5;
            }

            QPushButton#dangerButton {
                color: #FFEDEA;
                background-color: rgba(255, 111, 94, 95);
                border: 1px solid rgba(255, 145, 128, 130);
            }

            QScrollBar:vertical, QScrollBar:horizontal {
                background: transparent;
                border: none;
                margin: 0px;
            }

            QScrollBar:vertical {
                width: 8px;
            }

            QScrollBar:horizontal {
                height: 8px;
            }

            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 42);
                border-radius: 4px;
                min-height: 36px;
                min-width: 36px;
            }

            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: rgba(255, 255, 255, 75);
            }

            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {
                background: transparent;
                border: none;
            }
            """
        )
        
    def _make_sidebar_header(self):
        header = QWidget()
        header.setObjectName("sidebarHeader")

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignVCenter)

        icon_label = QLabel()
        icon_label.setObjectName("appIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setMinimumSize(72, 72)
        icon_label.setMaximumSize(72, 72)

        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "assets",
            "app-icon",
            "BirdBros-AppIcon-1024.png"
        )

        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)

            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(
                        72,
                        72,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                )
            else:
                icon_label.setText("🐦")
        else:
            icon_label.setText("🐦")

        text_stack = QWidget()
        text_stack.setObjectName("headerTextStack")
        text_stack.setMinimumWidth(210)
        text_stack.setMaximumWidth(250)
        text_stack.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        text_layout = QVBoxLayout(text_stack)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)
        text_layout.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)

        header_label = QLabel("BirdBros Recycle Co.")
        header_label.setObjectName("appHeader")
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setWordWrap(False)
        header_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        descriptor_line_one = QLabel("Autonomous Behaviour")
        descriptor_line_one.setObjectName("appDescriptorPrimary")
        descriptor_line_one.setAlignment(Qt.AlignCenter)
        descriptor_line_one.setWordWrap(False)
        descriptor_line_one.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        descriptor_line_two = QLabel("Reinforcement")
        descriptor_line_two.setObjectName("appDescriptor")
        descriptor_line_two.setAlignment(Qt.AlignCenter)
        descriptor_line_two.setWordWrap(False)
        descriptor_line_two.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        header_spacer = QLabel("")
        header_spacer.setObjectName("headerSpacer")
        header_spacer.setFixedHeight(4)

        text_layout.addWidget(header_label)
        text_layout.addWidget(header_spacer)
        text_layout.addWidget(descriptor_line_one)
        text_layout.addWidget(descriptor_line_two)

        text_area = QWidget()
        text_area.setObjectName("headerTextArea")
        text_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        text_area_layout = QHBoxLayout(text_area)
        text_area_layout.setContentsMargins(0, 0, 0, 0)
        text_area_layout.setSpacing(0)
        text_area_layout.setAlignment(Qt.AlignCenter)

        text_area_layout.addWidget(text_stack, 0, Qt.AlignCenter)

        layout.addWidget(icon_label, 0, Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(text_area, 1, Qt.AlignVCenter)

        return header
        
    def _make_collapsible_section(self, title, body_widget, expanded=False, icon_text="•"):
        section = QWidget()
        section.setObjectName("collapsibleSection")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("sectionHeaderCard")
        header.setCursor(Qt.PointingHandCursor)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header.setFixedHeight(58)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignVCenter)

        left_icon = QLabel(icon_text)
        left_icon.setObjectName("sectionSideIcon")
        left_icon.setAlignment(Qt.AlignCenter)
        left_icon.setFixedSize(42, 32)

        title_label = QLabel(title)
        title_label.setObjectName("sectionHeaderTitle")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_label.setFixedHeight(34)

        right_icon = QLabel("OPEN" if expanded else "MORE")
        right_icon.setObjectName("sectionSideIcon")
        right_icon.setAlignment(Qt.AlignCenter)
        right_icon.setFixedSize(42, 32)

        body_widget.setVisible(expanded)
        body_widget.setObjectName("sectionBody")
        body_widget.setMinimumWidth(0)
        body_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        expanded_state = {"value": expanded}

        def update_section_visibility(checked):
            expanded_state["value"] = checked
            body_widget.setVisible(checked)
            right_icon.setText("OPEN" if checked else "MORE")
            header.setProperty("expanded", checked)
            header.style().unpolish(header)
            header.style().polish(header)

        def toggle_section(event):
            update_section_visibility(not expanded_state["value"])
            event.accept()

        header_layout.addWidget(left_icon, 0, Qt.AlignLeft | Qt.AlignVCenter)
        header_layout.addWidget(title_label, 1, Qt.AlignCenter)
        header_layout.addWidget(right_icon, 0, Qt.AlignRight | Qt.AlignVCenter)

        header.mousePressEvent = toggle_section
        update_section_visibility(expanded)

        layout.addWidget(header)
        layout.addWidget(body_widget)

        return section
        
    def _make_spinbox(self, min_value, max_value):
        spin = QSpinBox()
        spin.setRange(min_value, max_value)
        spin.setSingleStep(1)
        spin.setButtonSymbols(QSpinBox.PlusMinus)
        spin.setMinimumWidth(64)
        spin.setMaximumWidth(108)
        spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return spin

    def _apply_capture_region_to_fields(self, capture_region):
        self.capture_left.setValue(capture_region.left)
        self.capture_top.setValue(capture_region.top)
        self.capture_width.setValue(capture_region.width)
        self.capture_height.setValue(capture_region.height)

    def _apply_subject_roi_to_fields(self, roi):
        self.subject_x.setValue(roi.x)
        self.subject_y.setValue(roi.y)
        self.subject_w.setValue(roi.width)
        self.subject_h.setValue(roi.height)

    def _apply_object_roi_to_fields(self, roi):
        self.object_x.setValue(roi.x)
        self.object_y.setValue(roi.y)
        self.object_w.setValue(roi.width)
        self.object_h.setValue(roi.height)

    def _make_reward_row(self, label_text, widget):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        label.setMinimumWidth(92)
        row_layout.addWidget(label, 0)
        row_layout.addWidget(widget, 1)

        return row

    def _make_full_width_reward_row(self, label_text, widget):
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        row_layout.addWidget(label)
        row_layout.addWidget(widget)

        return row

    def _apply_reward_action_visibility(self, action_type):
        mouse_visible = action_type == "mouse_click"
        keyboard_visible = action_type == "keyboard_shortcut"
        command_visible = action_type == "shell_command"
        webhook_visible = action_type == "webhook"

        # Legacy flat mouse fields stay hidden.
        # The dynamic click sequence is the active mouse-click UI.
        self.reward_x_row.setVisible(False)
        self.reward_y_row.setVisible(False)
        self.reward_clicks_row.setVisible(mouse_visible)
        self.reward_interval_row.setVisible(False)
        self.reward_move_duration_row.setVisible(False)
        self.reward_click_sequence_row.setVisible(mouse_visible)

        self.reward_keys_row.setVisible(keyboard_visible)

        self.reward_command_row.setVisible(command_visible)

        self.reward_url_row.setVisible(webhook_visible)
        self.reward_method_row.setVisible(webhook_visible)
        self.reward_timeout_row.setVisible(webhook_visible)
        self.reward_bearer_row.setVisible(webhook_visible)
        self.reward_headers_row.setVisible(webhook_visible)
        self.reward_payload_row.setVisible(webhook_visible)

        return {
            "mouse_visible": mouse_visible,
            "keyboard_visible": keyboard_visible,
            "command_visible": command_visible,
            "webhook_visible": webhook_visible,
        }

    def _apply_behavior_mode_visibility(self, mode):
        advanced_visible = mode == "advanced"

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

        return {
            "advanced_visible": advanced_visible,
        }

    def _apply_video_input_visibility(self, input_mode):
        video_file_visible = input_mode == "video_file"

        self.video_path_row.setVisible(video_file_visible)
        self.video_loop_row.setVisible(video_file_visible)

        return {
            "video_file_visible": video_file_visible,
        }

    def _make_click_sequence_step_row(self, index, step):
        row = QWidget()
        row.setObjectName("clickSequenceStep")

        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(6)

        title = QLabel(f"Click {index + 1}")
        title.setObjectName("clickSequenceTitle")

        x_spin = self._make_spinbox(0, 10000)
        y_spin = self._make_spinbox(0, 10000)
        hold_spin = self._make_spinbox(0, 10000)
        delay_spin = self._make_spinbox(0, 10000)
        move_spin = self._make_spinbox(0, 10000)

        for spinbox in [x_spin, y_spin, hold_spin, delay_spin, move_spin]:
            spinbox.setMinimumWidth(0)
            spinbox.setMaximumWidth(92)
            spinbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        x_spin.setValue(int(step.get("x", 735)))
        y_spin.setValue(int(step.get("y", 586)))
        hold_spin.setValue(int(float(step.get("hold_duration", 0.0)) * 1000))
        delay_spin.setValue(int(float(step.get("delay_after", 0.1)) * 1000))
        move_spin.setValue(int(float(step.get("move_duration", 0.0)) * 1000))

        position_layout = QGridLayout()
        position_layout.setContentsMargins(0, 0, 0, 0)
        position_layout.setHorizontalSpacing(8)
        position_layout.setVerticalSpacing(3)

        timing_layout = QGridLayout()
        timing_layout.setContentsMargins(0, 0, 0, 0)
        timing_layout.setHorizontalSpacing(8)
        timing_layout.setVerticalSpacing(3)

        capture_button = QPushButton("Capture Position")
        capture_button.setObjectName("secondaryButton")

        position_layout.addWidget(QLabel("X"), 0, 0)
        position_layout.addWidget(QLabel("Y"), 0, 1)
        position_layout.addWidget(x_spin, 1, 0)
        position_layout.addWidget(y_spin, 1, 1)
        position_layout.addWidget(capture_button, 2, 0, 1, 2)

        timing_layout.addWidget(QLabel("Hold ms"), 0, 0)
        timing_layout.addWidget(QLabel("Delay ms"), 0, 1)
        timing_layout.addWidget(QLabel("Move ms"), 0, 2)
        timing_layout.addWidget(hold_spin, 1, 0)
        timing_layout.addWidget(delay_spin, 1, 1)
        timing_layout.addWidget(move_spin, 1, 2)

        position_layout.setColumnStretch(0, 1)
        position_layout.setColumnStretch(1, 1)

        timing_layout.setColumnStretch(0, 1)
        timing_layout.setColumnStretch(1, 1)
        timing_layout.setColumnStretch(2, 1)

        row_layout.addWidget(title)
        row_layout.addLayout(position_layout)
        row_layout.addLayout(timing_layout)

        capture_button.clicked.connect(
            lambda: self._capture_click_sequence_position(x_spin, y_spin)
        )

        for spinbox in [x_spin, y_spin, hold_spin, delay_spin, move_spin]:
            spinbox.valueChanged.connect(self._on_widget_changed)

        return {
            "row": row,
            "x": x_spin,
            "y": y_spin,
            "capture_button": capture_button,
            "hold_duration": hold_spin,
            "delay_after": delay_spin,
            "move_duration": move_spin
        }
