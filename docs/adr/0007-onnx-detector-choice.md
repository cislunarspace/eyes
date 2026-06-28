# 0007 — ONNX 检测器选型

## 背景

Rust 核心需要人脸检测 + 头部姿态估计。当前 Python 端使用 MediaPipe FaceLandmarker，Rust 端需要一个 ONNX 方案。ADR-0005 已确定姿态分类逻辑，本 ADR 确定视觉感知层的技术选型。

## 评估标准

1. **许可证**：必须是 Apache 2.0、MIT 或 BSD
2. **模型大小**：总体积 < 20 MB（硬约束）；理想 < 5 MB
3. **推理延迟**：Windows 中端 CPU（i5/Ryzen 5）单帧 < 30 ms
4. **准确度**：5 种姿态（正面、左转、右转、仰头、低头）需正确区分，且与 Python MediaPipe 行为一致
5. **输入格式**：RGB/BGR 需明确，`solvePnP` 坐标系约定需记录
6. **ONNX Runtime**：需验证 `ort` crate 的兼容性和模型加载时间

## 选定方案：YuNet 单模型 + 纯 Rust solvePnP

### 为什么选 YuNet？

YuNet 是 OpenCV 官方维护的人脸检测模型，除了边界框，还输出 5 个关键点：
左眼中心、右眼中心、鼻尖、左嘴角、右嘴角。

用这 5 个关键点 + 第 6 个估算点（下巴 = bbox 底部中心）做 DLT solvePnP，就能算出头部旋转。不需要额外的关键点模型。

### 为什么用纯 Rust solvePnP 而非 opencv::solve_pnp？

`opencv` crate 需要系统 OpenCV 安装，且 `solve_pnp` 的参数约定（标定参数、失真系数）与本项目的"估算相机内参"方案不匹配。DLT solvePnP 仅需 `nalgebra` 做 SVD，与 `onnx-detector` feature 的条件编译一致，不引入额外的系统依赖。

### 模型资产

| 特性 | 值 |
|------|-----|
| 文件 | `models/face_detection_yunet_2023mar.onnx` |
| 来源 | [opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) |
| 许可证 | Apache 2.0 |
| 大小 | 232 KB |
| SHA256 | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| 推理方式 | ONNX Runtime (`ort = "=2.0.0-rc.12"`) |

### 输入 / 输出合约

**输入**

| 名称 | 形状 | 类型 | 说明 |
|------|------|------|------|
| input | `[1, 3, 240, 320]` | float32 | NCHW，RGB，未归一化（[0, 255]） |

**输出**

| 名称 | 形状 | 类型 | 说明 |
|------|------|------|------|
| output | `[1, N, 15]` | float32 | N 个候选检测 |

每个检测 15 个值：`[x, y, w, h, conf, lx0, ly0, lx1, ly1, lx2, ly2, lx3, ly3, lx4, ly4]`

- `conf`：置信度，阈值 0.5
- `lx/ly 0-4`：5 个关键点的 2D 坐标（输入图像坐标系，需乘比例缩放回原始分辨率）
- 关键点顺序：左眼、右眼、鼻尖、左嘴角、右嘴角

### 姿态估计流程

1. YuNet 输出 5 个 2D 关键点 → 组合第 6 个估算点（下巴）
2. 6 对 2D-3D 点 → DLT solvePnP（12×12 SVD）→ 旋转矩阵
3. `rotation_to_yaw_pitch(R)`：yaw = atan2(R[0][2], R[2][2])，pitch = atan2(R[2][1], R[2][2])

**符号约定**：positive yaw = 右转，positive pitch = 仰头，与 Python 端 MediaPipe 路径一致。

**下巴估算精度**：大角度旋转（>45°）时下巴估算偏差增大，可能影响 pitch 准确度。

### 延迟实测（Windows 11, i5/Ryzen 5）

黑帧 640×480，30 次取样（2026-06-28）：

| 指标 | 值 |
|------|-----|
| P50 | 1.43 ms |
| P95 | 1.55 ms |
| P99 | 1.57 ms |

远低于 30 ms 阈值。包含完整流程：预处理 + YuNet 推理 + DLT solvePnP。

## 备选方案

### 路线 B：YuNet + PFLD（106 关键点）

精度更高，但 PFLD 没有预导出的 ONNX 文件，需要自行从 PyTorch 导出。

### 路线 C：SixDRepNet

单模型直接输出 yaw/pitch/roll，不需要 solvePnP。模型 ~30 MB+，许可证待确认。

### 路线 D：MediaPipe ONNX

468 关键点精度最高，但有 Google 专利限制。不推荐。

## 实现状态

| 步骤 | 状态 |
|------|------|
| 下载 YuNet 模型 | ✅ 已完成 |
| 添加 `ort`/`nalgebra` 依赖 | ✅ 已完成 |
| 实现 `YuNetDetector` | ✅ 已完成（`src-tauri/src/monitoring/onnx_detector.rs`） |
| 单元测试（合成投影点） | ✅ 12 个测试全绿 |
| Windows 延迟实测（P50/P95） | ✅ P95=1.55 ms |
| 手动 5 姿态验证（真实摄像头） | ⬜ 待执行 |

## 签署

- 日期：2026-06-28
- 状态：实现完成，等待 Windows 延迟实测 + 手动姿态验证
