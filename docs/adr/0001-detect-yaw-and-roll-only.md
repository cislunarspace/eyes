# Detect yaw and roll only; ignore pitch and eye gaze

The product spec mentions both 歪头 (head tilt = roll) and 斜视 (eye gaze sideways). To keep the detector simple and robust, "Facing Screen" is operationalized as `|yaw| ≤ yaw_threshold AND |roll| ≤ roll_threshold` only. Pitch is ignored entirely — looking down at the keyboard or a notebook should not trigger an alarm. Eye-gaze tracking is out of scope; head-pose yaw is used as a coarse proxy for "looking at the screen".

## Considered Options

- **yaw + pitch + roll** — rejected: pitch alarms misfire on legitimate looking-down (keyboard, paper, phone briefly); finding a non-annoying pitch threshold is hard.
- **head pose + iris-based gaze estimation** — rejected: significantly more complex, sensitive to glasses/lighting/individual eye geometry, and not justified for v1 by the spec.

## Consequences

- The detector cannot tell apart "head facing screen with eyes wandering" from "head facing screen with eyes engaged" — both are reported as **Facing Screen**.
- Pure-roll deviation ("head tilted onto a shoulder") suppresses the periodic "良好" praise but does not produce a corrective prompt of its own.
