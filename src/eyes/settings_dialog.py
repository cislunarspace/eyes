"""SettingsDialog — composes form editor, calibration view, camera selector, and platform shell.

The dialog's responsibilities are limited to:
  1. Laying out a form with sliders, toggles, and combo boxes.
  2. Tracking pending changes against the original config.
  3. Composing `CalibrationView`, `CameraSelector`, and the
     `PlatformShell` from this module's neighbours.
  4. Saving the pending changes via `ConfigStore` on accept.
  5. Emitting `settings_changed` and `calibration_completed` signals.

The dialog no longer imports `subprocess`, `sys`, or `cv2`. The
calibration sequencer, camera probe, and platform shell all live in
their own modules.
"""

from __future__ import annotations

import os
from typing import Any

import platformdirs
from PySide6.QtCore import Qt, Signal
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

from .calibration_view import CalibrationView
from .camera_selector import CameraSelector, OpenCVCameraProbe
from .config_store import ConfigStore
from .i18n import t
from .platform_shell import PlatformShell, select_shell
from .runtime_timings import CALIBRATION_TICK_INTERVAL_MS

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

    def __init__(
        self,
        config_store: ConfigStore,
        parent: QWidget | None = None,
        *,
        camera_probe=None,
        platform_shell: PlatformShell | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._original_config = config_store.load()
        # Track pending changes separately since AppConfig is frozen.
        self._pending_changes: dict[str, Any] = {}
        # Calibration sequencer: a QWidget that owns the QTimer and
        # the CalibrationSession. The dialog drives it via start() and
        # reads countdown via session.countdown_seconds.
        self._calibration_view = CalibrationView(
            self, tick_interval_ms=CALIBRATION_TICK_INTERVAL_MS
        )
        # Platform shell: defaults to the current platform; the dialog
        # can be constructed with a different shell for tests.
        self._shell: PlatformShell = platform_shell or select_shell()

        self.setWindowTitle(f"Eyes — {t('settings.title')}")
        self.setMinimumWidth(400)
        self._camera_probe = camera_probe
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
        self._row_label_realtime_yaw = QLabel(t("settings.realtime_yaw"))
        self._row_label_realtime_pitch = QLabel(t("settings.realtime_pitch"))
        self._form_layout.addRow(self._row_label_realtime_yaw, self._realtime_yaw_label)
        self._form_layout.addRow(self._row_label_realtime_pitch, self._realtime_pitch_label)

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
        self._row_label_yaw = QLabel(t("settings.yaw_threshold"))
        self._form_layout.addRow(self._row_label_yaw, yaw_layout)

        # Off-axis streak threshold slider
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
        self._row_label_streak = QLabel(t("settings.first_prompt_delay"))
        self._form_layout.addRow(self._row_label_streak, streak_layout)

        # Off-axis repeat interval slider
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
        self._row_label_repeat = QLabel(t("settings.repeat_prompt_interval"))
        self._form_layout.addRow(self._row_label_repeat, repeat_layout)

        # Roll threshold slider
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
        self._row_label_roll = QLabel(t("settings.pitch_threshold"))
        self._form_layout.addRow(self._row_label_roll, pitch_layout)

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
        self._row_label_neutral = QLabel(t("settings.neutral_pose"))
        self._form_layout.addRow(self._row_label_neutral, pose_layout)

        # Calibration countdown label
        self._countdown_label = QLabel("")
        self._countdown_label.setStyleSheet("color: #ff6600; font-weight: bold;")
        self._form_layout.addRow("", self._countdown_label)

        # Camera selector: QComboBox populated from a CameraProbe.
        self._camera_combo = self._build_camera_selector()
        self._row_label_camera = QLabel(t("settings.camera"))
        self._form_layout.addRow(self._row_label_camera, self._camera_combo)

        # Sound toggle
        self._sound_toggle = QPushButton(
            t("settings.on") if self._get_value("sound_enabled", False) else t("settings.off")
        )
        self._sound_toggle.setCheckable(True)
        self._sound_toggle.setChecked(self._get_value("sound_enabled", False))
        self._sound_toggle.clicked.connect(self._on_sound_toggled)
        self._row_label_sound = QLabel(t("settings.sound"))
        self._form_layout.addRow(self._row_label_sound, self._sound_toggle)

        # Autostart toggle
        self._autostart_toggle = QPushButton(
            t("settings.on") if self._get_value("autostart_enabled", False) else t("settings.off")
        )
        self._autostart_toggle.setCheckable(True)
        self._autostart_toggle.setChecked(self._get_value("autostart_enabled", False))
        self._autostart_toggle.clicked.connect(self._on_autostart_toggled)
        self._row_label_autostart = QLabel(t("settings.autostart"))
        self._form_layout.addRow(self._row_label_autostart, self._autostart_toggle)

        # Language selector
        self._language_combo = QComboBox()
        for label_text, lang_value in _LANGUAGE_ITEMS:
            self._language_combo.addItem(label_text, lang_value)
        current_lang = self._get_value("language", "zh-CN")
        lang_idx = self._language_combo.findData(current_lang)
        if lang_idx >= 0:
            self._language_combo.setCurrentIndex(lang_idx)
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        self._row_label_language = QLabel(t("settings.language"))
        self._form_layout.addRow(self._row_label_language, self._language_combo)

        # Open data directory button
        self._open_dir_button = QPushButton(t("settings.open_data_directory"))
        self._open_dir_button.clicked.connect(self._open_data_directory)
        self._row_label_data_dir = QLabel(t("settings.data_directory"))
        self._form_layout.addRow(self._row_label_data_dir, self._open_dir_button)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self._on_accept)
        main_layout.addWidget(button_box)

    def _build_camera_selector(self) -> CameraSelector:
        """Build a CameraSelector from the chosen probe (or the default OpenCV probe)."""
        probe = self._camera_probe or OpenCVCameraProbe()
        return CameraSelector(probe=probe, current_index=int(self._get_value("camera_index", 0)))

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
        """Start a 5-second calibration countdown via the calibration view."""
        self._calibration_view.start()
        self._calibrate_button.setEnabled(False)
        self._update_countdown_label()
        self.calibration_started.emit()

    def _update_countdown_label(self) -> None:
        """Update the countdown label to the current session seconds."""
        seconds = int(self._calibration_view.session.countdown_seconds)
        if self._calibration_view.is_calibrating:
            # Show seconds remaining; the original used +1 because it
            # updated the label at the END of each tick.
            self._countdown_label.setText(
                t("calibration.in_progress").format(seconds=seconds + 1)
            )
        else:
            self._countdown_label.setText(t("calibration.complete"))

    def _finish_calibration(self) -> None:
        """Apply the calibration result and update the dialog labels."""
        result = self._calibration_view.session.result()
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

        Returns True if the session was active and accepted the sample.
        The controller calls this each tick while the dialog is open.
        """
        if not self._calibration_view.is_calibrating:
            return False
        self._calibration_view.feed(yaw, roll)
        return True

    def is_calibrating(self) -> bool:
        return self._calibration_view.is_calibrating

    def _open_data_directory(self) -> None:
        """Open the user data directory in the platform file manager."""
        data_dir = platformdirs.user_config_dir("eyes")
        os.makedirs(data_dir, exist_ok=True)
        self._shell.open(data_dir)

    def _on_accept(self) -> None:
        """Save settings and close dialog."""
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
        # Also update the countdown label if calibration is running.
        if self._calibration_view.is_calibrating:
            self._update_countdown_label()

    def refresh_language(self) -> None:
        """Re-read all i18n strings and update visible labels.

        Fixes the documented "does not refresh during the current session"
        behavior. Call this after ``set_language()`` changes the
        process-wide language.
        """
        self.setWindowTitle(f"Eyes — {t('settings.title')}")

        # Form row labels — stored as explicit QLabel refs.
        self._row_label_realtime_yaw.setText(t("settings.realtime_yaw"))
        self._row_label_realtime_pitch.setText(t("settings.realtime_pitch"))
        self._row_label_yaw.setText(t("settings.yaw_threshold"))
        self._row_label_streak.setText(t("settings.first_prompt_delay"))
        self._row_label_repeat.setText(t("settings.repeat_prompt_interval"))
        self._row_label_roll.setText(t("settings.pitch_threshold"))
        self._row_label_neutral.setText(t("settings.neutral_pose"))
        self._row_label_camera.setText(t("settings.camera"))
        self._row_label_sound.setText(t("settings.sound"))
        self._row_label_autostart.setText(t("settings.autostart"))
        self._row_label_language.setText(t("settings.language"))
        self._row_label_data_dir.setText(t("settings.data_directory"))

        # Buttons whose text is controlled by i18n.
        self._calibrate_button.setText(t("settings.calibrate_button"))
        self._open_dir_button.setText(t("settings.open_data_directory"))
        self._sound_toggle.setText(
            t("settings.on") if self._get_value("sound_enabled", False) else t("settings.off")
        )
        self._autostart_toggle.setText(
            t("settings.on") if self._get_value("autostart_enabled", False) else t("settings.off")
        )

        # Camera selector: re-populate with the new language's text.
        current_camera = self._get_value("camera_index", 0)
        self._camera_combo.refresh(current_camera)

        # Countdown label (only meaningful while calibration is running).
        if self._calibration_view.is_calibrating:
            self._update_countdown_label()
