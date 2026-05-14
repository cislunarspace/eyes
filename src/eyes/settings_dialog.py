"""Settings dialog for configuring app parameters."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import platformdirs
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from eyes.calibration import CalibrationSession
from eyes.config_store import ConfigStore
from eyes.i18n import t

# Slider ranges
_YAW_SLIDER_MIN = 1
_YAW_SLIDER_MAX = 30
_YAW_SLIDER_TICK = 5
_ROLL_SLIDER_MIN = 5
_ROLL_SLIDER_MAX = 30
_ROLL_SLIDER_TICK = 5
_STREAK_SLIDER_MIN = 0
_STREAK_SLIDER_MAX = 30
_STREAK_SLIDER_TICK = 5
_REPEAT_SLIDER_MIN = 10
_REPEAT_SLIDER_MAX = 120
_REPEAT_SLIDER_TICK = 10

_LANGUAGE_ITEMS = [("中文", "zh-CN"), ("English", "en")]


class SettingsDialog(QDialog):
    """Settings dialog with controls for yaw/roll thresholds, calibration, camera, and sound.

    Signals:
        settings_changed: Emitted when any setting is changed and saved.
        calibration_started: Emitted when calibration countdown begins.
        calibration_completed: Emitted when calibration finishes with (yaw, roll) result.
    """

    settings_changed = Signal()
    calibration_started = Signal()
    calibration_completed = Signal(float, float)

    def __init__(self, config_store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._original_config = config_store.load()
        # Track pending changes separately since AppConfig is frozen
        self._pending_changes: dict[str, Any] = {}
        # Session owns samples + countdown; this dialog only drives the QTimer
        # and observes session state for UI updates.
        self._calibration_session = CalibrationSession(duration_seconds=5.0)
        self._calibration_timer: QTimer | None = None

        self.setWindowTitle(f"Eyes — {t('settings.title')}")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _get_value(self, key: str, default: Any) -> Any:
        """Get value from pending changes or original config."""
        return self._pending_changes.get(key, getattr(self._original_config, key))

    def _set_value(self, key: str, value: Any) -> None:
        """Set a pending change."""
        self._pending_changes[key] = value

    def _setup_ui(self) -> None:
        """Build the settings form: sliders, calibration controls, camera selector, and toggles."""
        main_layout = QVBoxLayout(self)
        self._form_layout = QFormLayout()
        main_layout.addLayout(self._form_layout)

        # Real-time pose display
        self._realtime_yaw_label = QLabel("--")
        self._realtime_pitch_label = QLabel("--")
        self._form_layout.addRow(t("settings.realtime_yaw"), self._realtime_yaw_label)
        self._form_layout.addRow(t("settings.realtime_pitch"), self._realtime_pitch_label)

        # Yaw threshold slider
        yaw_layout = QHBoxLayout()
        self._yaw_slider = QSlider()
        self._yaw_slider.setOrientation(Qt.Orientation.Horizontal)
        self._yaw_slider.setMinimum(_YAW_SLIDER_MIN)
        self._yaw_slider.setMaximum(_YAW_SLIDER_MAX)
        self._yaw_slider.setValue(int(self._get_value("yaw_threshold", 1.0)))
        self._yaw_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._yaw_slider.setTickInterval(_YAW_SLIDER_TICK)
        self._yaw_slider.valueChanged.connect(self._on_yaw_changed)
        self._yaw_value_label = QLabel(f"{self._get_value('yaw_threshold', 1.0):.0f}°")
        yaw_layout.addWidget(self._yaw_slider)
        yaw_layout.addWidget(self._yaw_value_label)
        self._form_layout.addRow(t("settings.yaw_threshold"), yaw_layout)

        # Off-axis streak threshold slider (首次提示等待时间)
        streak_layout = QHBoxLayout()
        self._streak_slider = QSlider()
        self._streak_slider.setOrientation(Qt.Orientation.Horizontal)
        self._streak_slider.setMinimum(_STREAK_SLIDER_MIN)
        self._streak_slider.setMaximum(_STREAK_SLIDER_MAX)
        self._streak_slider.setValue(int(self._get_value("off_axis_streak_threshold_seconds", 1.0)))
        self._streak_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._streak_slider.setTickInterval(_STREAK_SLIDER_TICK)
        self._streak_slider.valueChanged.connect(self._on_streak_threshold_changed)
        self._streak_value_label = QLabel(f"{self._get_value('off_axis_streak_threshold_seconds', 1.0):.0f}s")
        streak_layout.addWidget(self._streak_slider)
        streak_layout.addWidget(self._streak_value_label)
        self._form_layout.addRow(t("settings.first_prompt_delay"), streak_layout)

        # Off-axis repeat interval slider (重复提示间隔)
        repeat_layout = QHBoxLayout()
        self._repeat_slider = QSlider()
        self._repeat_slider.setOrientation(Qt.Orientation.Horizontal)
        self._repeat_slider.setMinimum(_REPEAT_SLIDER_MIN)
        self._repeat_slider.setMaximum(_REPEAT_SLIDER_MAX)
        self._repeat_slider.setValue(int(self._get_value("off_axis_repeat_interval_seconds", 10.0)))
        self._repeat_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._repeat_slider.setTickInterval(_REPEAT_SLIDER_TICK)
        self._repeat_slider.valueChanged.connect(self._on_repeat_interval_changed)
        self._repeat_value_label = QLabel(f"{self._get_value('off_axis_repeat_interval_seconds', 10.0):.0f}s")
        repeat_layout.addWidget(self._repeat_slider)
        repeat_layout.addWidget(self._repeat_value_label)
        self._form_layout.addRow(t("settings.repeat_prompt_interval"), repeat_layout)

        # Pitch threshold slider (俯仰阈值)
        pitch_layout = QHBoxLayout()
        self._roll_slider = QSlider()
        self._roll_slider.setOrientation(Qt.Orientation.Horizontal)
        self._roll_slider.setMinimum(_ROLL_SLIDER_MIN)
        self._roll_slider.setMaximum(_ROLL_SLIDER_MAX)
        self._roll_slider.setValue(int(self._get_value("roll_threshold", 5.0)))
        self._roll_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._roll_slider.setTickInterval(_ROLL_SLIDER_TICK)
        self._roll_slider.valueChanged.connect(self._on_roll_changed)
        self._roll_value_label = QLabel(f"{self._get_value('roll_threshold', 5.0):.0f}°")
        pitch_layout.addWidget(self._roll_slider)
        pitch_layout.addWidget(self._roll_value_label)
        self._form_layout.addRow(t("settings.pitch_threshold"), pitch_layout)

        # Neutral pose display and calibrate button
        pose_layout = QHBoxLayout()
        self._neutral_pose_label = QLabel(
            f"({self._get_value('neutral_yaw', 0.0):+.1f}°, {self._get_value('neutral_roll', 0.0):+.1f}°)"
        )
        self._calibrate_button = QPushButton(t("settings.calibrate_button"))
        self._calibrate_button.clicked.connect(self._start_calibration)
        pose_layout.addWidget(self._neutral_pose_label)
        pose_layout.addWidget(self._calibrate_button)
        pose_layout.addStretch()
        self._form_layout.addRow(t("settings.neutral_pose"), pose_layout)

        # Calibration countdown label
        self._countdown_label = QLabel("")
        self._countdown_label.setStyleSheet("color: #ff6600; font-weight: bold;")
        self._form_layout.addRow("", self._countdown_label)

        # Camera selector
        self._camera_combo = QComboBox()
        self._populate_camera_list()
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        self._form_layout.addRow(t("settings.camera"), self._camera_combo)

        # Sound toggle
        self._sound_toggle = QPushButton(
            t("settings.on") if self._get_value("sound_enabled", False) else t("settings.off")
        )
        self._sound_toggle.setCheckable(True)
        self._sound_toggle.setChecked(self._get_value("sound_enabled", False))
        self._sound_toggle.clicked.connect(self._on_sound_toggled)
        self._form_layout.addRow(t("settings.sound"), self._sound_toggle)

        # Autostart toggle
        self._autostart_toggle = QPushButton(
            t("settings.on") if self._get_value("autostart_enabled", False) else t("settings.off")
        )
        self._autostart_toggle.setCheckable(True)
        self._autostart_toggle.setChecked(self._get_value("autostart_enabled", False))
        self._autostart_toggle.clicked.connect(self._on_autostart_toggled)
        self._form_layout.addRow(t("settings.autostart"), self._autostart_toggle)

        # Language selector (combo box with pending change tracking)
        self._language_combo = QComboBox()
        for label_text, lang_value in _LANGUAGE_ITEMS:
            self._language_combo.addItem(label_text, lang_value)
        current_lang = self._get_value("language", "zh-CN")
        lang_idx = self._language_combo.findData(current_lang)
        if lang_idx >= 0:
            self._language_combo.setCurrentIndex(lang_idx)
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        self._form_layout.addRow(t("settings.language"), self._language_combo)

        # Open data directory button
        self._open_dir_button = QPushButton(t("settings.open_data_directory"))
        self._open_dir_button.clicked.connect(self._open_data_directory)
        self._form_layout.addRow(t("settings.data_directory"), self._open_dir_button)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self._on_accept)
        main_layout.addWidget(button_box)

    def _populate_camera_list(self) -> None:
        """Populate camera dropdown with available cameras."""
        self._camera_combo.clear()
        available_cameras = []

        # Try to detect cameras
        for i in range(5):  # Check first 5 indices
            try:
                import cv2
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    available_cameras.append(i)
                    cap.release()
            except Exception:
                break

        for idx in available_cameras:
            self._camera_combo.addItem(t("settings.camera_index").format(index=idx), idx)

        # Select current camera
        current_camera = self._get_value("camera_index", 0)
        current_idx = self._camera_combo.findData(current_camera)
        if current_idx >= 0:
            self._camera_combo.setCurrentIndex(current_idx)

    def _on_yaw_changed(self, value: int) -> None:
        self._yaw_value_label.setText(f"{value}°")
        self._set_value("yaw_threshold", float(value))

    def _on_streak_threshold_changed(self, value: int) -> None:
        self._streak_value_label.setText(f"{value}s")
        self._set_value("off_axis_streak_threshold_seconds", float(value))

    def _on_repeat_interval_changed(self, value: int) -> None:
        self._repeat_value_label.setText(f"{value}s")
        self._set_value("off_axis_repeat_interval_seconds", float(value))

    def _on_roll_changed(self, value: int) -> None:
        self._roll_value_label.setText(f"{value}°")
        self._set_value("roll_threshold", float(value))

    def _on_camera_changed(self, index: int) -> None:
        if index >= 0:
            camera_idx = self._camera_combo.itemData(index)
            self._set_value("camera_index", camera_idx)

    def _on_sound_toggled(self, checked: bool) -> None:
        self._set_value("sound_enabled", checked)
        self._sound_toggle.setText(t("settings.on") if checked else t("settings.off"))

    def _on_autostart_toggled(self, checked: bool) -> None:
        self._set_value("autostart_enabled", checked)
        self._autostart_toggle.setText(t("settings.on") if checked else t("settings.off"))

    def _on_language_changed(self, index: int) -> None:
        if index >= 0:
            lang_value = self._language_combo.itemData(index)
            self._set_value("language", lang_value)

    def _start_calibration(self) -> None:
        """Start 5-second calibration countdown."""
        self._calibration_session.start()
        self._calibrate_button.setEnabled(False)
        self._countdown_label.setText(
            t("calibration.in_progress").format(
                seconds=int(self._calibration_session.countdown_seconds)
            )
        )
        self.calibration_started.emit()

        # Start sampling timer (every 100ms = 10 Hz)
        self._calibration_timer = QTimer()
        self._calibration_timer.timeout.connect(self._calibration_tick)
        self._calibration_timer.start(100)  # 10 Hz sampling

    def _calibration_tick(self) -> None:
        """Process one calibration tick; advance the session and refresh UI."""
        self._calibration_session.tick(0.1)

        if not self._calibration_session.is_active:
            self._finish_calibration()
            return

        self._countdown_label.setText(
            t("calibration.in_progress").format(
                seconds=int(self._calibration_session.countdown_seconds) + 1
            )
        )

    def _finish_calibration(self) -> None:
        """Finish calibration: stop timer and publish the session's result."""
        if self._calibration_timer:
            self._calibration_timer.stop()
            self._calibration_timer = None

        result = self._calibration_session.result()
        if result is not None:
            self._set_value("neutral_yaw", result.yaw)
            self._set_value("neutral_roll", result.roll)
            self._neutral_pose_label.setText(
                f"({result.yaw:+.1f}°, {result.roll:+.1f}°)"
            )
            self.calibration_completed.emit(result.yaw, result.roll)

        self._calibrate_button.setEnabled(True)
        self._countdown_label.setText(t("calibration.complete"))

    def add_calibration_sample(self, yaw: float, roll: float) -> bool:
        """Forward a pose sample to the active calibration session.

        Called by AppController during calibration.
        Returns True if the session was active and accepted the sample.
        """
        if not self._calibration_session.is_active:
            return False
        self._calibration_session.feed(yaw, roll)
        return True

    def is_calibrating(self) -> bool:
        """Return True if calibration is in progress."""
        return self._calibration_session.is_active

    def _open_data_directory(self) -> None:
        """Open the user data directory in file explorer."""
        data_dir = platformdirs.user_config_dir("eyes")
        # Ensure directory exists
        os.makedirs(data_dir, exist_ok=True)
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", data_dir])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", data_dir])
            else:
                subprocess.Popen(["xdg-open", data_dir])
        except Exception:
            pass

    def _on_accept(self) -> None:
        """Save settings and close dialog."""
        # Apply all pending changes
        if self._pending_changes:
            self._config_store.update(**self._pending_changes)
        self.settings_changed.emit()
        self.accept()

    def get_pending_camera_index(self) -> int | None:
        """Return pending camera index if changed, None otherwise."""
        return self._pending_changes.get("camera_index")

    def update_current_pose(self, yaw: float | None, pitch: float | None) -> None:
        """Update the real-time pose display. Called by controller each tick."""
        if yaw is not None:
            self._realtime_yaw_label.setText(f"{yaw:+.1f}°")
        else:
            self._realtime_yaw_label.setText("--")
        if pitch is not None:
            self._realtime_pitch_label.setText(f"{pitch:+.1f}°")
        else:
            self._realtime_pitch_label.setText("--")

    def refresh_language(self) -> None:
        """Refresh all UI text after language change.

        Note: Settings dialog does not refresh during the current session.
        This method is provided for interface consistency but the dialog
        keeps the language it was opened with.
        """
        pass
