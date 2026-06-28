# 0007 — ONNX 检测器选型

Rust 重写需要用 ONNX 模型替换 Python 的 MediaPipe FaceLandmarker。本 ADR 记录候选方案、评估标准和最终选型。

## 评估标准

1. **许可证**：必须可重新分发（Apache 2.0、MIT、BSD），不含商业限制。
2. **模型大小**：所有模型资产合计 < 50 MB（理想 < 20 MB），适合打包进 Windows 安装包。
3. **推理延迟**：Windows 桌面级 CPU（i5/Ryzen 5 级别）单帧 < 30 ms。
4. **精度**：5 种姿态（正对、左转、右转、仰头、低头）的分类结果与 Python MediaPipe 版本行为一致。
5. **输入输出**：接受 BGR/RGB 图像，输出足够信息用于 `solvePnP` 或直接输出 yaw/pitch。
6. **ONNX 兼容性**：通过 `ort` crate 可正常加载和推理。

## 候选方案

### 路径 A：人脸检测 + 关键点 + solvePnP（两阶段）

默认路径（ADR-0005）。先检测人脸，再定位关键点，最后通过 `solvePnP` 计算旋转矩阵。

**人脸检测模型**：

| 模型 | 来源 | 许可证 | 大小 | 备注 |
|------|------|--------|------|------|
| SCRFD | InsightFace | MIT | ~1-5 MB | 高精度，多尺度，社区广泛使用 |
| YuNet | OpenCV | Apache 2.0 | ~0.2 MB | 超轻量，OpenCV 内置，精度够用 |
| RetinaFace-ONNX | 社区 | MIT | ~1-2 MB | 经典方案，但比 SCRFD 老 |

**关键点模型**：

| 模型 | 来源 | 许可证 | 大小 | 关键点数 | 备注 |
|------|------|--------|------|----------|------|
| PFLD | 社区 | MIT | ~1-3 MB | 98/106 | 轻量，移动端友好 |
| MediaPipe Face Mesh ONNX | Google | Apache 2.0 | ~3 MB | 478 | 精度高，但 ONNX 导出需验证 |
| MobileFaceNet | 社区 | MIT | ~1 MB | 5/68 | 极轻量，关键点少 |

**评估步骤**：
1. 导出/下载 SCRFD (320×240) 和 PFLD ONNX 模型
2. 用 `ort` crate 加载，测量加载时间和推理延迟
3. `solvePnP` 计算旋转矩阵，复用 `rotation_to_yaw_roll` 逻辑
4. 5 种姿态手动测试

### 路径 B：直接头部姿态估计（单阶段）

端到端模型，输入图像直接输出 yaw/pitch/roll。

| 模型 | 来源 | 许可证 | 大小 | 备注 |
|------|------|--------|------|------|
| SixDRepNet | 学术 | MIT | ~30 MB | 精度高，但模型较大 |
| FSANet | 学术 | MIT | ~2 MB | 轻量，精度一般 |
| HopeNet | 学术 | MIT | ~5 MB | 经典，但较老 |

**评估步骤**：
1. 导出 SixDRepNet ONNX 模型
2. 用 `ort` crate 加载，测量延迟
3. 5 种姿态手动测试，与 Python MediaPipe 对比

### 路径 C：MediaPipe ONNX 导出

将 MediaPipe FaceLandmarker 导出为 ONNX 格式，复用现有旋转矩阵逻辑。

**优点**：行为最接近 Python 版本，旋转数学可直接复用。
**缺点**：MediaPipe 模型格式（.task）不是标准 ONNX，导出过程复杂且可能违反许可证。

**结论**：不推荐。MediaPipe 的 .task 格式是自定义的，不是标准 ONNX protobuf。

## 默认选择

**路径 A：YuNet（人脸检测）+ PFLD（关键点）+ OpenCV solvePnP**

理由：
- YuNet 极轻量（~0.2 MB），Apache 2.0 许可，OpenCV 内置
- PFLD 轻量（~1-3 MB），MIT 许可，98/106 关键点足够
- `solvePnP` 逻辑可复用，旋转矩阵到 yaw/pitch 的转换已有 Python 实现
- 总模型大小 < 5 MB，远低于 50 MB 预算
- 两阶段架构便于调试和替换

**后备方案**：SixDRepNet（单阶段，模型较大但精度高）。

## 决策

**待定** — 需要人工 spike 验证。

## 资产清单

待 spike 完成后填写：

| 模型 | 文件名 | SHA256 | 来源 URL | 许可证 | 大小 |
|------|--------|--------|----------|--------|------|
| YuNet | TBD | TBD | TBD | Apache 2.0 | ~0.2 MB |
| PFLD | TBD | TBD | TBD | MIT | ~1-3 MB |

## 输入输出约定

待 spike 验证后填写：

```
YuNet:
  输入: BGR 图像 (H×W×3), uint8
  输出: 人脸边界框 [x, y, w, h] + 5 个关键点（可选）

PFLD:
  输入: 裁剪后的人脸 BGR 图像, uint8
  输出: 98/106 个 2D 关键点 [(x, y), ...]

solvePnP:
  输入: 2D 关键点 + 3D 模型点
  输出: 旋转向量 → 旋转矩阵 → yaw/pitch
```

## 延迟数据

待 spike 测量后填写。

## 后果

- 如果 YuNet + PFLD 路径通过 spike，总模型大小 < 5 MB，打包成本极低。
- 如果精度不满足要求，升级到 SCRFD + MediaPipe Face Mesh ONNX（~8 MB）或 SixDRepNet（~30 MB）。
- 旋转矩阵到 yaw/pitch 的转换逻辑（`head_pose_geometry.py`）需要移植为 Rust 实现。
- 所有候选方案都需要 `ort` crate 和 OpenCV（用于 `solvePnP` 和图像预处理）。
