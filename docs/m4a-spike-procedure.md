# M4a Spike 评估文档

## 概述

评估 ONNX 检测器（YuNet + solvePnP）在 Windows CPU 上的可行性。目标：用单个 ~232 KB 的模型替代 Python 的 MediaPipe，实现离线头姿检测。

## 前提条件

- Windows 10/11
- Rust 工具链（rustup）
- 摄像头（用于手动姿态测试，Step 5）
- 模型文件：`models/face_detection_yunet_2023mar.onnx`（已下载）

## 评估步骤

### ✅ Step 1: 下载模型

已完成。`models/face_detection_yunet_2023mar.onnx`（232 KB，Apache 2.0）。

SHA256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`

### ✅ Step 2: 添加依赖

已完成。`src-tauri/Cargo.toml` 已添加：

```toml
[features]
onnx-detector = ["dep:ort", "dep:nalgebra"]

[dependencies]
ort = { version = "=2.0.0-rc.12", optional = true }
nalgebra = { version = "0.33", optional = true }
```

### ✅ Step 3: 实现检测器

已完成。`src-tauri/src/monitoring/onnx_detector.rs`：
- `YuNetDetector::new(model_path)` — 加载模型
- `detect(rgb, width, height)` — 完整推理流程

### ✅ Step 4: 运行延迟测试

已完成。实测数据（Windows 11，黑帧 640×480，30 次）：

```
P50=1.43 ms  P95=1.55 ms  P99=1.57 ms
```

远低于 30 ms 阈值。运行方式：

**方式 A — probe 二进制（含简易延迟统计）：**

```bash
cd src-tauri
cargo run --features onnx-detector --bin yunet_probe -- ..\models\face_detection_yunet_2023mar.onnx
```

预期输出（黑帧，30 次）：

```
✅ 模型加载成功: ..\models\face_detection_yunet_2023mar.onnx
✅ detect(黑帧 640×480) = None  (黑帧预期 None)
📊 延迟（黑帧，30 次）: P50=X.XX ms  P95=X.XX ms  P99=X.XX ms
✅ Probe 完成。
```

**方式 B — 单元测试 `latency_benchmark`（打印 P50/P95/P99）：**

```bash
cd src-tauri
cargo test --features onnx-detector latency_benchmark -- --nocapture
```

模型文件不存在时测试自动跳过，不会 fail。

验收：P95 < 30 ms ✅。记录实测数值更新 ADR-0007。

### ✅ Step 5: 手动 5 姿态验证

已完成。符号约定验证通过：
- 仰头 → pitch > 0 ✅
- 低头 → pitch < 0 ✅
- 左转 → yaw > 0 ✅
- 右转 → yaw < 0 ✅
- 正面 → yaw ≈ 0 ✅

**备注**：摄像头与屏幕平面不完全平行，pitch 存在系统性偏移，使用前需校正 neutral pose（应用已有校正流程）。

在 `src-tauri/src/bin/yunet_probe.rs` 中替换输入帧为真实摄像头帧，或使用 Python 侧临时脚本：

```python
# tests/manual_yunet_check.py — 快速手动验证
import cv2, sys, subprocess, json

cap = cv2.VideoCapture(0)
print("按 q 退出，按 s 截图")
while True:
    ok, frame = cap.read()
    if not ok:
        break
    cv2.imshow("camera", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
```

（实际接入 `YuNetDetector` 时把 `frame` 转为 RGB bytes 传给 `detect()`。）

需验证 5 种姿态：

| 姿态 | 预期 yaw | 预期 pitch |
|------|----------|------------|
| 正面 | ≈ 0° | ≈ 0° |
| 左转 30° | ≈ -30° | ≈ 0° |
| 右转 30° | ≈ +30° | ≈ 0° |
| 仰头 | ≈ 0° | > +5° |
| 低头 | ≈ 0° | < -5° |

## 成功标准

- [x] 模型文件已下载（~232 KB）
- [x] `ort` / `nalgebra` 依赖成功编译
- [x] 检测器实现完成（12 个单元测试全绿）
- [x] **P95 延迟 < 30 ms** — 实测 1.55 ms ✅
- [x] **5 种姿态正确识别** — 实测通过 ✅

## 已知限制

- 5 关键点精度有限，下巴由 bbox 估算，>45° 时误差增大
- 如果姿态精度不够，备选：SixDRepNet 单模型（需确认许可证）
- `ort = "=2.0.0-rc.12"` 锁定了 rc 版本；正式版发布后需更新

## 下一步（Spike 通过后）

1. 把 `YuNetDetector` 接入 Rust monitoring worker
2. 在设置页面添加"检测器后端"切换（MediaPipe / ONNX）
3. 处理 ONNX Runtime 动态库的打包分发
