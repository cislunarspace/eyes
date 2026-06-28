# M4a Spike 评估文档

## 概述

评估 ONNX 检测器（YuNet + solvePnP）在 Windows CPU 上的可行性。目标：用单个 ~232 KB 的模型替代 Python 的 MediaPipe，实现离线头姿检测。

## 前提条件

- Windows 10/11
- Rust 工具链（rustup）
- 摄像头（用于手动姿态测试）
- 模型文件：`models/face_detection_yunet_2023mar.onnx`（已下载）

## 评估步骤

### Step 1: 确认模型文件

验证 `models/face_detection_yunet_2023mar.onnx` 存在且大小合理（~232 KB）。

### Step 2: 添加依赖

在 `src-tauri/Cargo.toml` 中添加：

```toml
[dependencies]
ort = "2"  # ONNX Runtime Rust 绑定

[features]
onnx-detector = []  # 可选功能，控制是否编译 ONNX 检测器
```

注意：`ort` crate 会自动下载 ONNX Runtime 动态库（~15 MB），首次构建较慢。

### Step 3: 实现检测器

在 `src-tauri/src/monitoring/onnx_detector.rs` 中填充：

1. `YuNetDetector::new()` — 加载 ONNX 模型
2. `detect()` — 完整推理流程：
   - 预处理：RGB → 320×240 float32
   - YuNet 推理：获取边界框 + 5 关键点
   - solvePnP：5 个 2D 关键点 + 5 个 3D 模型点 → 旋转矩阵
   - 提取 yaw 和 pitch

### Step 4: 延迟测试

```bash
cargo test --features onnx-detector --test onnx_detector_spike -- --nocapture
```

预期输出：

```
YuNet 推理延迟:
  P50: 8.2 ms
  P95: 14.5 ms
  P99: 18.3 ms
solvePnP 延迟: 0.05 ms
总延迟 P95: 14.6 ms
✅ 低于 30 ms 阈值
```

如果 P95 > 30 ms，需要优化（降低输入分辨率、量化模型等）。

### Step 5: 手动姿态测试

用摄像头运行 5 种姿态，验证输出：

| 姿态 | 预期输出 |
|------|----------|
| 正面 | yaw ≈ 0, pitch ≈ 0 |
| 左转 30° | yaw ≈ -30 |
| 右转 30° | yaw ≈ 30 |
| 仰头 | pitch > 0 |
| 低头 | pitch < 0 |

对比 Python 端 MediaPipe 的输出，确认符号约定一致。

## 成功标准

- [x] 模型文件已下载（~232 KB）
- [ ] `ort` 依赖成功编译
- [ ] 检测器实现完成
- [ ] P95 延迟 < 30 ms
- [ ] 5 种姿态正确识别
- [ ] 符号约定与 Python 端一致

## 已知限制

- 5 关键点精度有限，头部大角度旋转（>60°）时可能不稳定
- 如果精度不够，可考虑增加 PFLD 模型做 106 关键点（需自行导出 ONNX）
- `ort` crate 首次构建会下载 ~15 MB 的 ONNX Runtime 动态库

## 下一步

Spike 通过后：

1. 实现 `detector.rs` 的 `YuNetDetector` 完整版本
2. 添加 `--features onnx-detector` 到 CI 构建
3. 在设置页面添加"检测器选择"下拉框
4. 处理 `ort` 动态库的打包和分发
