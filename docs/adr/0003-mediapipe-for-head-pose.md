# 0003 — 用 MediaPipe FaceLandmarker 做头部姿态检测

头部姿态检测通过 Google 的 MediaPipe FaceLandmarker（Tasks API）实现，每帧返回一个面部变换矩阵和 478 个 3D 关键点。偏航和横滚从旋转矩阵的旋转部分提取（或等价地，从单位基分解）。选择 MediaPipe 的原因：许可宽松（Apache 2.0）、单条 `pip install` 跨平台交付（Windows + Linux + x86 + ARM）、无需 GPU 的实时 CPU 性能、活跃维护的上游。

## 考虑过的选项

- **OpenCV 人脸检测 + dlib 68 关键点 + `cv2.solvePnP`** — 否决：dlib 在 Windows 上需要 CMake 构建 wheel，CPU 上比 MediaPipe 慢，部分遮挡（眼镜、手）时检测精度更低。
- **预训练 ONNX 头部姿态模型（6DRepNet / FSA-Net / WHENet）** — 否决：需要打包模型权重和 `onnxruntime`，增加打包体积，且回归式模型不提供面部网格，无法用于后续更丰富的功能（眼睛开合度、眨眼计数等）。

## 后果

- 项目现在依赖 `mediapipe`。替换它意味着重写检测模块并重新审视阈值语义（不同模型在不同尺度上产生偏航/横滚）。
- 打包二进制体积因 MediaPipe 的内置资源增加约 20-30 MB——作为代价接受。
- 未来受益于同一网格的功能（眨眼率、基于眼纵横比的疲劳检测）现在添加成本很低。
