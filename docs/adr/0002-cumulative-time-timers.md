# Periodic prompts trigger on cumulative time, not wall-clock

The user-facing spec says "每 5 分钟" and "每 15 分钟", but the canonical reading in this project is **cumulative time in the relevant state**, not wall-clock time since startup. The 5-minute "良好" prompt fires once the **Facing Time Accumulator** reaches 300s of accumulated **Facing Screen** time. The 15-minute "请眺望远方" prompt fires once the **Presence Time Accumulator** reaches 900s of accumulated **Face Detected** time. Both accumulators pause when their gating signal is false and reset to zero on each fire.

## Considered Options

- **Wall-clock tick (every N minutes since app start)** — rejected: feels arbitrary; users who just sat down would have to wait until the next tick to be acknowledged, and the eye-rest reminder would fire while the user was away from the desk.
- **Continuous-streak (must be uninterrupted)** — rejected: too strict; brief deviations (water sip, glance at phone) reset the streak and the user effectively never qualifies.

## Consequences

- The 5-minute prompt rewards proportional facing-screen time, even with short interruptions.
- The 15-minute eye-rest counts time the user is at the screen *in any pose*, including off-axis — strain accumulates whether or not the head is perfectly aligned.
- The two accumulators run on different signals and reset independently — they will not align in time, which is intentional.
