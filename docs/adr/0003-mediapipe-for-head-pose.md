# Use MediaPipe FaceLandmarker for head-pose detection

Head-pose detection is implemented via Google's MediaPipe FaceLandmarker (Tasks API), which returns a face transformation matrix and 478 3D landmarks per frame. Yaw and roll are extracted from the rotation portion of that matrix (or, equivalently, decomposed from the unit basis). MediaPipe was chosen for permissive licensing (Apache 2.0), single `pip install` cross-platform delivery on Windows + Linux + x86 + ARM, real-time CPU performance without GPU, and an actively maintained upstream.

## Considered Options

- **OpenCV face detector + dlib 68 landmarks + `cv2.solvePnP`** — rejected: dlib requires CMake to build wheels on Windows, slower than MediaPipe on CPU, and detection accuracy is lower on partial occlusions (glasses, hands).
- **Pretrained ONNX head-pose model (6DRepNet / FSA-Net / WHENet)** — rejected: requires bundling model weights and `onnxruntime`, increases packaging surface, and the regression-style models do not give us a face mesh that we can later use for richer features (eye openness, blink counting, etc.).

## Consequences

- The project is now coupled to `mediapipe`. Replacing it would mean rewriting the detection module and revisiting the threshold semantics (a different model produces yaw/roll on a different scale).
- Packaged binary size grows by ~20-30 MB from MediaPipe's bundled assets — accept as the cost.
- Future features that benefit from the same mesh (blink rate, eye-aspect-ratio-based fatigue detection) are now low-cost to add.
