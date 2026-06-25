"""i18n module — translation dictionary with t() and set_language().

Module-level ``t()`` and ``set_language()`` operate on a process-wide
language variable. ``current_language`` is a plain module attribute
readable from anywhere.
"""

from __future__ import annotations

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh-CN": {
        # overlay
        "overlay.adjust_left": "向左调整",
        "overlay.adjust_right": "向右调整",
        "overlay.good_posture": "当前姿势良好",
        "overlay.eye_rest": "请眺望远方",
        "overlay.corrected": "姿势良好",
        # settings
        "settings.title": "设置",
        "settings.realtime_yaw": "实时偏航",
        "settings.realtime_pitch": "实时俯仰",
        "settings.yaw_threshold": "偏航阈值",
        "settings.first_prompt_delay": "首次提示延迟",
        "settings.repeat_prompt_interval": "重复提示间隔",
        "settings.pitch_threshold": "俯仰阈值",
        "settings.neutral_pose": "中立姿态",
        "settings.calibrate_button": "校准中立姿态",
        "settings.camera": "摄像头",
        "settings.camera_index": "摄像头 {index}",
        "settings.sound": "提示音",
        "settings.autostart": "开机自启",
        "settings.language": "语言",
        "settings.data_directory": "数据目录",
        "settings.open_data_directory": "打开数据目录",
        "settings.on": "开启",
        "settings.off": "关闭",
        # tray
        "tray.show_window": "显示窗口",
        "tray.pause_30": "暂停 30 分钟",
        "tray.pause_1h": "暂停 1 小时",
        "tray.pause_indefinite": "暂停至恢复",
        "tray.resume": "恢复",
        "tray.open_settings": "打开设置",
        "tray.quit": "退出",
        "tray.tooltip_active": "Eyes — 监控中",
        "tray.tooltip_paused": "Eyes — 已暂停",
        "tray.tooltip_unavailable": "Eyes — 摄像头不可用",
        # main_window
        "main_window.camera_unavailable": "摄像头被其他程序占用…等待恢复",
        "main_window.please_face_screen": "请正视屏幕",
        "main_window.adjust_left_hint": "← 请向左调整",
        "main_window.adjust_right_hint": "→ 请向右调整",
        "main_window.posture_good": "姿势良好 ✓",
        "main_window.readout_placeholder": "yaw: —   roll: —",
        # badge
        "badge.facing_screen": "头正对",
        "badge.off_axis_left": "头左偏",
        "badge.off_axis_right": "头右偏",
        "badge.off_axis_other": "头偏转",
        "badge.no_face": "未检测到人脸",
        # calibration
        "calibration.in_progress": "校准中... {seconds}秒",
        "calibration.complete": "校准完成!",
        # readout
        "readout.label": "yaw",
    },
    "en": {
        # overlay
        "overlay.adjust_left": "Adjust Left",
        "overlay.adjust_right": "Adjust Right",
        "overlay.good_posture": "Good Posture",
        "overlay.eye_rest": "Look Into the Distance",
        "overlay.corrected": "Posture Corrected",
        # settings
        "settings.title": "Settings",
        "settings.realtime_yaw": "Live Yaw",
        "settings.realtime_pitch": "Live Pitch",
        "settings.yaw_threshold": "Yaw Threshold",
        "settings.first_prompt_delay": "First Prompt Delay",
        "settings.repeat_prompt_interval": "Repeat Prompt Interval",
        "settings.pitch_threshold": "Pitch Threshold",
        "settings.neutral_pose": "Neutral Pose",
        "settings.calibrate_button": "Calibrate Neutral Pose",
        "settings.camera": "Camera",
        "settings.camera_index": "Camera {index}",
        "settings.sound": "Alert Sound",
        "settings.autostart": "Launch at Startup",
        "settings.language": "Language",
        "settings.data_directory": "Data Directory",
        "settings.open_data_directory": "Open Data Directory",
        "settings.on": "On",
        "settings.off": "Off",
        # tray
        "tray.show_window": "Show Window",
        "tray.pause_30": "Pause 30 Minutes",
        "tray.pause_1h": "Pause 1 Hour",
        "tray.pause_indefinite": "Pause Until I Resume",
        "tray.resume": "Resume",
        "tray.open_settings": "Open Settings",
        "tray.quit": "Quit",
        "tray.tooltip_active": "Eyes — Monitoring",
        "tray.tooltip_paused": "Eyes — Paused",
        "tray.tooltip_unavailable": "Eyes — Camera Unavailable",
        # main_window
        "main_window.camera_unavailable": "Camera is in use by another app… Waiting",
        "main_window.please_face_screen": "Please Face the Screen",
        "main_window.adjust_left_hint": "← Adjust Left",
        "main_window.adjust_right_hint": "→ Adjust Right",
        "main_window.posture_good": "Good Posture ✓",
        "main_window.readout_placeholder": "yaw: —   roll: —",
        # badge
        "badge.facing_screen": "Facing Screen",
        "badge.off_axis_left": "Turned Left",
        "badge.off_axis_right": "Turned Right",
        "badge.off_axis_other": "Tilted",
        "badge.no_face": "No Face Detected",
        # calibration
        "calibration.in_progress": "Calibrating... {seconds}s",
        "calibration.complete": "Calibration Complete!",
        # readout
        "readout.label": "yaw",
    },
}


# Process-wide language state.
current_language: str = "zh-CN"


def set_language(lang: str) -> None:
    """Set the process-wide default language."""
    global current_language
    current_language = lang


def t(key: str) -> str:
    """Look up a translation key using the process-wide default language."""
    return _TRANSLATIONS[current_language][key]
