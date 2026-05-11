"""Settings dialog for configuring app parameters."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

import platformdirs
from PySide6.QtCore import QTimer, Signal
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

from eyes.calibration import PoseSample, compute_median_pose
from eyes.config_store import ConfigStore
from eyes.types import AppConfig


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
        self._calibration_samples: list[PoseSample] = []
        self._calibration_timer: QTimer | None = None
        self._calibration_countdown = 5.0

        self.setWindowTitle("设置")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _get_value(self, key: str, default: Any) -> Any:
        """Get value from pending changes or original config."""
        return self._pending_changes.get(key, getattr(self._original_config, key))

    def _set_value(self, key: str, value: Any) -> None:
        """Set a pending change."""
        self._pending_changes[key] = value

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        self._form_layout = QFormLayout()
        main_layout.addLayout(self._form_layout)

        # Yaw threshold slider
        yaw_layout = QHBoxLayout()
        self._yaw_slider = QSlider()
        self._yaw_slider.setOrientation(1)  # Horizontal
        self._yaw_slider.setMinimum(1)
        self._yaw_slider.setMaximum(30)
        self._yaw_slider.setValue(int(self._get_value("yaw_threshold", 1.0)))
        self._yaw_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._yaw_slider.setTickInterval(5)
        self._yaw_slider.valueChanged.connect(self._on_yaw_changed)
        self._yaw_value_label = QLabel(f"{self._get_value('yaw_threshold', 1.0):.0f}°")
        yaw_layout.addWidget(self._yaw_slider)
        yaw_layout.addWidget(self._yaw_value_label)
        self._form_layout.addRow("偏航阈值", yaw_layout)

        # Roll threshold slider (disabled: roll no longer affects classification)
        roll_layout = QHBoxLayout()
        self._roll_slider = QSlider()
        self._roll_slider.setOrientation(1)
        self._roll_slider.setMinimum(5)
        self._roll_slider.setMaximum(30)
        self._roll_slider.setValue(int(self._get_value("roll_threshold", 90.0)))
        self._roll_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._roll_slider.setTickInterval(5)
        self._roll_slider.valueChanged.connect(self._on_roll_changed)
        self._roll_value_label = QLabel(f"{self._get_value('roll_threshold', 90.0):.0f}° (已禁用)")
        roll_layout.addWidget(self._roll_slider)
        roll_layout.addWidget(self._roll_value_label)
        self._form_layout.addRow("翻滚阈值 (已禁用)", roll_layout)

        # Neutral pose display and calibrate button
        pose_layout = QHBoxLayout()
        self._neutral_pose_label = QLabel(
            f"({self._get_value('neutral_yaw', 0.0):+.1f}°, {self._get_value('neutral_roll', 0.0):+.1f}°)"
        )
        self._calibrate_button = QPushButton("校准中立姿态")
        self._calibrate_button.clicked.connect(self._start_calibration)
        pose_layout.addWidget(self._neutral_pose_label)
        pose_layout.addWidget(self._calibrate_button)
        pose_layout.addStretch()
        self._form_layout.addRow("中立姿态", pose_layout)

        # Calibration countdown label
        self._countdown_label = QLabel("")
        self._countdown_label.setStyleSheet("color: #ff6600; font-weight: bold;")
        self._form_layout.addRow("", self._countdown_label)

        # Camera selector
        self._camera_combo = QComboBox()
        self._populate_camera_list()
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        self._form_layout.addRow("摄像头", self._camera_combo)

        # Sound toggle
        self._sound_toggle = QPushButton("开启" if self._get_value("sound_enabled", False) else "关闭")
        self._sound_toggle.setCheckable(True)
        self._sound_toggle.setChecked(self._get_value("sound_enabled", False))
        self._sound_toggle.clicked.connect(self._on_sound_toggled)
        self._form_layout.addRow("提示音", self._sound_toggle)

        # Autostart toggle
        self._autostart_toggle = QPushButton("开启" if self._get_value("autostart_enabled", False) else "关闭")
        self._autostart_toggle.setCheckable(True)
        self._autostart_toggle.setChecked(self._get_value("autostart_enabled", False))
        self._autostart_toggle.clicked.connect(self._on_autostart_toggled)
        self._form_layout.addRow("开机自启", self._autostart_toggle)

        # Language display (read-only)
        self._language_label = QLabel(self._get_value("language", "zh-CN"))
        self._form_layout.addRow("语言", self._language_label)

        # Open data directory button
        self._open_dir_button = QPushButton("打开数据目录")
        self._open_dir_button.clicked.connect(self._open_data_directory)
        self._form_layout.addRow("数据目录", self._open_dir_button)

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
            self._camera_combo.addItem(f"摄像头 {idx}", idx)

        # Select current camera
        current_camera = self._get_value("camera_index", 0)
        current_idx = self._camera_combo.findData(current_camera)
        if current_idx >= 0:
            self._camera_combo.setCurrentIndex(current_idx)

    def _on_yaw_changed(self, value: int) -> None:
        self._yaw_value_label.setText(f"{value}°")
        self._set_value("yaw_threshold", float(value))

    def _on_roll_changed(self, value: int) -> None:
        self._roll_value_label.setText(f"{value}°")
        self._set_value("roll_threshold", float(value))

    def _on_camera_changed(self, index: int) -> None:
        if index >= 0:
            camera_idx = self._camera_combo.itemData(index)
            self._set_value("camera_index", camera_idx)

    def _on_sound_toggled(self, checked: bool) -> None:
        self._set_value("sound_enabled", checked)
        self._sound_toggle.setText("开启" if checked else "关闭")

    def _on_autostart_toggled(self, checked: bool) -> None:
        self._set_value("autostart_enabled", checked)
        self._autostart_toggle.setText("开启" if checked else "关闭")

    def _start_calibration(self) -> None:
        """Start 5-second calibration countdown."""
        self._calibration_samples = []
        self._calibration_countdown = 5.0
        self._calibrate_button.setEnabled(False)
        self._countdown_label.setText(f"校准中... {int(self._calibration_countdown)}秒")
        self.calibration_started.emit()

        # Start sampling timer (every 100ms = 10 Hz)
        self._calibration_timer = QTimer()
        self._calibration_timer.timeout.connect(self._calibration_tick)
        self._calibration_timer.start(100)  # 10 Hz sampling

    def _calibration_tick(self) -> None:
        """Process one calibration tick."""
        self._calibration_countdown -= 0.1

        if self._calibration_countdown <= 0:
            self._finish_calibration()
            return

        self._countdown_label.setText(f"校准中... {int(self._calibration_countdown) + 1}秒")

    def _finish_calibration(self) -> None:
        """Finish calibration and compute median."""
        if self._calibration_timer:
            self._calibration_timer.stop()
            self._calibration_timer = None

        if self._calibration_samples:
            median = compute_median_pose(self._calibration_samples)
            self._set_value("neutral_yaw", median.yaw)
            self._set_value("neutral_roll", median.roll)
            self._neutral_pose_label.setText(
                f"({median.yaw:+.1f}°, {median.roll:+.1f}°)"
            )
            self.calibration_completed.emit(median.yaw, median.roll)

        self._calibrate_button.setEnabled(True)
        self._countdown_label.setText("校准完成!")

    def add_calibration_sample(self, yaw: float, roll: float) -> bool:
        """Add a pose sample during calibration.

        Called by AppController during calibration.
        Returns True if calibration is still in progress.
        """
        if self.is_calibrating() and self._calibration_samples is not None:
            self._calibration_samples.append(PoseSample(yaw=yaw, roll=roll))
            return True
        return False

    def is_calibrating(self) -> bool:
        """Return True if calibration is in progress."""
        return self._calibration_timer is not None and self._calibration_timer.isActive()

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
