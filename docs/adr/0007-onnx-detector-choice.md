# 0007 — ONNX 检测器选型

## 背景

Rust 核心需要人脸检测 + 头部姿态估计。当前 Python 端使用 MediaPipe FaceLandmarker，Rust 端需要一个 ONNX 方案。ADR-0005 已确定姿态分类逻辑，本 ADR 确定视觉感知层的技术选型。

## 评估标准

1. **许可证**：必须是 Apache 2.0、MIT 或 BSD
2. **模型大小**：总体积 < 5 MB（理想 < 20 MB），Windows 分发体积敏感
3. **推理延迟**：Windows 中端 CPU（i5/Ryzen 5）单帧 < 30 ms
4. **准确度**：5 种姿态（正面、左转、右转、仰头、低头）需正确区分，且与 Python MediaPipe 行为一致
5. **输入格式**：RGB/BGR 需明确，`solvePnP` 坐标系约定需记录
6. **ONNX Runtime**：需验证 `ort` crate 的兼容性和模型加载时间

## 推荐方案：YuNet 单模型 + solvePnP

### 为什么选 YuNet？

YuNet 是 OpenCV 官方维护的人脸检测模型，除了边界框，还输出 5 个关键点：
- 左眼中心
- 右眼中心
- 鼻尖
- 左嘴角
- 右嘴角

用这 5 个关键点 + 3D 模型点做 `solvePnP`，就能算出头部旋转。不需要额外的关键点模型。

| 特性 | 值 |
|------|-----|
| 来源 | OpenCV Zoo |
| 许可证 | Apache 2.0 |
| 大小 | ~232 KB |
| 输入 | 320×240 RGB float32 |
| 输出 | 边界框 + 5 关键点 + confidence |
| 推理方式 | ONNX Runtime (ort crate) |

### 关键点 → solvePnP → yaw/pitch

1. YuNet 输出 5 个 2D 关键点
2. 对应 5 个标准 3D 模型点（鼻尖为原点）
3. 调用 OpenCV `solvePnP` 得到旋转向量
4. 转旋转矩阵，提取 yaw 和 pitch

### 延迟预估

- YuNet 推理：~5-15 ms（CPU，取决于分辨率）
- solvePnP：~0.1 ms（纯数学运算）
- 总计：~5-15 ms，远低于 30 ms 阈值

### 如果 5 关键点不够准

备选：增加 PFLD 模型做 106 关键点。但 PFLD 没有预导出的 ONNX 文件，需要自行导出。建议先用 5 关键点验证，不够再加。

## 备选方案

### 路线 B：SixDRepNet

单模型直接输出 yaw/pitch/roll，不需要关键点和 solvePnP。但模型较大（~30MB+），且许可证需确认。适合作为路线 A 准确度不够时的备选。

### 路线 C：MediaPipe ONNX

468 关键点精度最高，但模型最大（~4MB），且有 Google 专利限制。不推荐。

## 实现方案

### 零配置分发

`models/face_detection_yunet_2023mar.onnx`（~232 KB）打包进安装包，首次启动即用。

### 依赖

- `ort` crate（ONNX Runtime Rust 绑定）
- OpenCV Rust 绑定（用于 `solvePnP`）或纯 Rust 实现

### 代码位置

- 检测器实现：`src-tauri/src/monitoring/onnx_detector.rs`
- 模块注册：`src-tauri/src/monitoring/mod.rs`（`#[cfg(feature = "onnx-detector")]`）

## Spike 验证步骤

1. ✅ 下载 YuNet 模型到 `models/`（已下载）
2. 在 Cargo.toml 中添加 `ort` 依赖
3. 实现 `YuNetDetector::new()` 和 `detect()`
4. 运行延迟测试，记录 P50/P95
5. 手动测试 5 种姿态，与 Python 端对比

## 签署

- 日期：2026-06-28
- 状态：Spike 进行中
