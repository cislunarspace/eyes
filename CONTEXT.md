# Eyes

A desktop application that uses a webcam to monitor a user's head pose in real time and prompts them when their posture deviates from facing the screen, or when it's time for a periodic eye-rest break.

## Language

**Head Pose**:
Orientation of the user's head relative to the camera, expressed as two angles: yaw and roll. Pitch is intentionally ignored.
_Avoid_: posture, head orientation, head angle

**Yaw**:
Rotation of the head about the vertical axis — turning the head left or right.
_Avoid_: pan, horizontal rotation

**Roll**:
Tilt of the head about the forward (camera-facing) axis — tilting the head sideways toward a shoulder.
_Avoid_: tilt, lean (these are ambiguous)

**Facing Screen** (正对屏幕):
The state where the user's **Head Pose** has both `|yaw| ≤ yaw_threshold` and `|roll| ≤ roll_threshold`. Note: this approximates "eyes looking at the screen" using head pose only — true gaze tracking is not in scope.
_Avoid_: looking at screen, eyes on screen, attentive

**Off-Axis Left** (头偏左):
**Head Pose** in which yaw indicates the head has turned to the user's own left beyond `yaw_threshold`. Triggers the "向右调整" prompt.
_Avoid_: turned left, leaning left, looking left

**Off-Axis Right** (头偏右):
**Head Pose** in which yaw indicates the head has turned to the user's own right beyond `yaw_threshold`. Triggers the "向左调整" prompt.
_Avoid_: turned right, leaning right, looking right

**Face Detected**:
At least one face is found in the current camera frame. The signal that drives the **Presence Time Accumulator**, independent of whether the user is **Facing Screen**.
_Avoid_: user present, user at desk

**Facing Time Accumulator**:
Cumulative duration spent in the **Facing Screen** state since the last "良好" prompt. Increments at +1s/s while **Facing Screen**, pauses otherwise. Resets to zero when it reaches 300s and the prompt fires.
_Avoid_: posture timer, good-posture clock

**Presence Time Accumulator**:
Cumulative duration during which **Face Detected** is true since the last "请眺望远方" prompt. Increments at +1s/s while a face is detected, pauses when no face. Resets to zero when it reaches 900s and the prompt fires. Independent of yaw/roll.
_Avoid_: eye-rest timer, screen-time clock

**Neutral Pose**:
The yaw/roll pair that, for this user on this device, represents the canonical "facing the screen" posture. All deviation comparisons (Off-Axis checks) are computed relative to **Neutral Pose**, not absolute zero. Defaults to (0°, 0°); user can recapture by holding a relaxed forward-looking pose for 5 seconds.
_Avoid_: zero pose, baseline, calibration point

**Off-Axis Streak**:
The continuous duration the user has remained in **Off-Axis Left** or **Off-Axis Right** without returning to **Facing Screen** or **Face Detected** flipping false. Used to debounce corrective prompts: first prompt fires when the streak reaches 5 seconds; while still off-axis, the prompt repeats every 30 seconds. Reset to zero on any return to **Facing Screen** or any **Face Detected** false.
_Avoid_: deviation duration, off-axis timer

## Relationships

- A **Head Pose** has exactly one yaw value and one roll value, sampled per video frame.
- **Facing Screen** is a derived state computed from a single **Head Pose** sample, evaluated relative to **Neutral Pose**.
- **Off-Axis Left** and **Off-Axis Right** are mutually exclusive; both are negations of **Facing Screen** along the yaw axis.
- **Facing Time Accumulator** advances only when the current frame's state is **Facing Screen**.
- **Presence Time Accumulator** advances whenever **Face Detected** is true, regardless of yaw/roll. The two accumulators run in parallel and reset independently.
- **Off-Axis Streak** advances only while the user is in **Off-Axis Left** or **Off-Axis Right**; resets the moment they exit.

## Flagged ambiguities

- "斜视" in the original spec literally means _eye gaze sideways_, but the project approximates this with head-pose yaw only. Future readers should not assume true gaze tracking exists.
- "偏左 / 偏右" perspective: defined here from the **user's own** point of view, not the camera's mirror image. The camera sees the opposite — sign convention in code must be explicit.
- "每 5 分钟提示" / "每 15 分钟提醒" are *cumulative*, not wall-clock — see **Facing Time Accumulator** and **Presence Time Accumulator**. Earlier readings of the spec might assume a wall-clock interpretation; the cumulative reading is canonical.

## Example dialogue

> **Dev:** "If the user turns their head to their own left, what does the app show?"
> **Product:** "It says '请向右调整' — it's telling them to rotate back toward the screen."
> **Dev:** "And if they tilt their head sideways onto a shoulder without turning?"
> **Product:** "That's high **Roll**, low yaw — still not **Facing Screen**, so the user just doesn't get the periodic '良好' praise. There's no dedicated corrective prompt for roll-only deviation."
