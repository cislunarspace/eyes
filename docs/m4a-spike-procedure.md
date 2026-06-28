# M4a Spike 评估流程

## 前置条件

- Windows 桌面机器（i5/Ryzen 5 级别 CPU）
- Rust 工具链已安装
- 摄像头可用

## 步骤 1：准备模型

### YuNet 人脸检测模型

从 OpenCV 的模型仓库下载：
- 文件：`face_detection_yunet_2023mar.onnx`
- 来源：https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet_2023mar
- 许可证：Apache 2.0
- 大小：约 0.2 MB

```bash
# 放到 models/ 目录
mkdir -p models
curl -L -o models/face_detection_yunet_2023mar.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet_2023mar/face_detection_yunet_2023mar.onnx
```

### PFLD 关键点模型

从 PFLD 的社区导出版本获取：
- 文件：`pfld_inference.onnx`
- 来源：https://github.com/Hsintao/PFLD-pytorch （需导出为 ONNX）
- 许可证：MIT
- 大小：约 1-3 MB

备选（如果 PFLD 导出困难）：
- 使用 MediaPipe Face Mesh 的 ONNX 导出版本
- 或使用 OpenCV 内置的 `Facemark` API

## 步骤 2：添加依赖

在 `src-tauri/Cargo.toml` 中添加：

```toml
[dependencies]
ort = "2"

[features]
default = []
onnx-detector = ["dep:ort"]
```

## 步骤 3：运行延迟测试

```bash
cd src-tauri
cargo test --features onnx-detector --test onnx_detector_spike -- --nocapture
```

预期输出：
- 模型加载时间
- 单帧推理延迟（应 < 30 ms）
- 5 种姿态的分类结果

## 步骤 4：手动姿态测试

在评估脚本中添加摄像头循环：

1. 正对摄像头 → 应输出 yaw ≈ 0°, pitch ≈ 0°
2. 头向左转 30° → 应输出 yaw ≈ -30°
3. 头向右转 30° → 应输出 yaw ≈ +30°
4. 仰头 20° → 应输出 pitch ≈ +20°
5. 低头 20° → 应输出 pitch ≈ -20°

## 步骤 5：记录结果

在 ADR-0007 中填写：
- [ ] 模型文件名和 SHA256
- [ ] 模型大小
- [ ] 推理延迟（ms）
- [ ] 5 种姿态的精度对比
- [ ] 最终选型决定

## 故障排除

### YuNet 加载失败
- 检查 ONNX 版本兼容性（ort crate 支持的 opset 版本）
- 尝试用 Netron 打开模型查看输入输出 shape

### PFLD 精度不够
- 升级到 SCRFD + MediaPipe Face Mesh ONNX（更大但更准）
- 或直接使用 SixDRepNet（单阶段，跳过关键点）

### 延迟超标
- 检查是否在 debug 模式运行（应使用 release）
- 尝试降低输入分辨率（320×240 而非 640×480）
- 检查是否启用了 ONNX Runtime 的 CPU 优化
