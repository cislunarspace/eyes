import type { TranslationKey } from './zh';

const en: Record<TranslationKey, string> = {
  // Settings
  'settings.title': 'Settings',
  'settings.yaw_threshold': 'Yaw Threshold (°)',
  'settings.pitch_threshold': 'Pitch Threshold (°)',
  'settings.camera_index': 'Camera',
  'settings.camera_0': 'Camera 0',
  'settings.camera_1': 'Camera 1',
  'settings.camera_2': 'Camera 2',
  'settings.language': 'Language',
  'settings.sound_enabled': 'Sound',
  'settings.autostart_enabled': 'Start at Login',
  'settings.calibrate': 'Calibrate Neutral Pose',
  'settings.save': 'Save',
  'settings.cancel': 'Cancel',
  'settings.saved': 'Saved',
  'settings.advanced': 'Advanced',
  'settings.streak_threshold': 'First Prompt Delay (s)',
  'settings.repeat_interval': 'Repeat Interval (s)',

  // Calibration
  'calibration.countdown': '{seconds}s remaining',
  'calibration.samples': '{count} frames sampled',
  'calibration.starting': 'Face the screen and hold still…',
  'calibration.success': 'Calibration complete! Neutral pose updated.',
  'calibration.no_face': 'Calibration failed: no face detected. Please retry.',
  'calibration.cancel': 'Cancel Calibration',

  // Main
  'main.title': 'Eyes',
  'main.subtitle': 'Tauri shell is running. Camera, pose detection, and reminders will be added in later milestones.',
  'main.settings': 'Settings',

  // Pose states
  'pose.facing_screen': 'Facing Screen',
  'pose.off_axis_left': 'Off-Axis Left',
  'pose.off_axis_right': 'Off-Axis Right',
  'pose.head_up': 'Head Up',
  'pose.head_down': 'Head Down',
  'pose.no_face': 'No Face Detected',

  // Warning levels
  'warning.normal': 'Normal',
  'warning.warning': 'Warning',
  'warning.severe': 'Severe',
  'warning.corrected': 'Corrected',

  // Direction hints
  'direction.left': 'Turn left',
  'direction.right': 'Turn right',
  'direction.face_screen': 'Please face the screen',
  'direction.adjust_left': 'Please turn left',
  'direction.adjust_right': 'Please turn right',

  // Camera state
  'camera.available': 'Camera Connected',
  'camera.unavailable': 'Camera Unavailable',
  'camera.starting': 'Connecting Camera…',

  // Snooze
  'snooze.paused': 'Reminders Paused',
  'snooze.resume': 'Resume Reminders',
  'snooze.30min': 'Pause 30 min',
  'snooze.1hour': 'Pause 1 hour',
  'snooze.indefinite': 'Pause Indefinitely',
};

export default en;
