# Eyes 护眼助手

一款桌面应用，用摄像头实时监测你的头部姿态，在你偏离屏幕方向时提醒你调整，或定时提示你让眼睛休息一下。

## 功能特点

- **实时头部姿态检测** - 调用 MediaPipe FaceLandmarker，利用摄像头捕捉画面
- **偏航角和翻滚角追踪** - 偏航角（左右转头）和翻滚角（头部倾斜）实时显示
- **姿态状态分类** - 分为：正对屏幕、偏左、偏右、其他偏离、无检测到人脸
- **中立姿态校准** - 保持放松的正对屏幕姿势 5 秒，即可设为个人基准
- **阈值可调节** - 根据个人习惯调整偏航角和翻滚角的容忍范围
- **定时姿态表扬** - 累计正对屏幕时长达到 300 秒时，提示"良好"给予正向反馈
- **防抖提醒机制** - 偏离屏幕 5 秒后首次提醒，之后每 30 秒重复提醒
- **PySide6 图形界面** - 实时摄像头预览、彩色状态徽章、角度数值显示

## 系统要求

- **操作系统**：Windows、macOS 或 Linux
- **Python**：3.12 或更高版本
- **摄像头**：任意可被 OpenCV 访问的摄像头（默认为摄像头索引 0）
- **依赖库**：MediaPipe、OpenCV、PySide6（随安装自动安装）

## 安装

### 从 PyPI 安装

```bash
pip install eyes
```

MediaPipe 模型会在首次运行时自动下载。

### 从源码安装

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
pip install .
```

### 开发模式安装

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
pip install -e ".[dev]"
```

## 使用方法

```bash
python -m eyes
python -m eyes 0          # 显式指定默认摄像头
python -m eyes 1          # 使用第二个摄像头
```

启动后，窗口会显示：

- **实时摄像头预览** - 你的摄像头画面
- **彩色徽章** - 当前姿态状态（绿色 = 正对屏幕，红色 = 偏离，橙色 = 仅翻滚角偏离，灰色 = 未检测到人脸）
- **角度数值** - 实时的偏航角和翻滚角（单位：度，如 `yaw: -3.2 deg   roll: +1.1 deg`）

### 中立姿态校准

运行应用时，保持放松的正对屏幕姿势 5 秒。应用会自动检测并记录这个稳定的前方姿势，作为后续所有偏离判断的基准。这样无论你相对摄像头的坐姿角度如何，应用都能准确工作。

## 配置

### 默认阈值

| 参数         | 默认值    | 说明                                              |
| ----------- | -------- | ------------------------------------------------ |
| `yaw_deg`   | 15.0 deg    | 偏航角容忍范围 - 超出此值判定为偏离                  |
| `roll_deg`  | 10.0 deg    | 翻滚角容忍范围 - 超出此值判定为翻滚角偏离             |
| 中立姿态     | (0 deg, 0 deg) | 正对屏幕的标准基准，支持通过校准重新设定              |

### 修改阈值

目前阈值的配置方式是直接编辑 `src/eyes/classifier.py`：

```python
@dataclass(frozen=True)
class Thresholds:
    yaw_deg: float = 15.0   # 在这里调整
    roll_deg: float = 10.0  # 在这里调整
```

未来版本会提供配置文件或图形界面来调整这些参数。

## 架构设计

### 项目结构

```text
eyes/
├── models/
│   └── face_landmarker.task    # MediaPipe 人脸特征点模型
├── src/eyes/
│   ├── __init__.py            # 包入口，版本号
│   ├── camera.py              # CameraSource - 通过 OpenCV 读取摄像头
│   ├── detector.py            # HeadPoseDetector - MediaPipe 封装，返回 (yaw, roll)
│   ├── classifier.py          # PoseClassifier - 纯函数：(yaw, roll) → PoseState
│   ├── main_window.py         # MainWindow - PySide6 图形界面，预览、读数、徽章
│   └── controller.py          # AppController - 10 Hz 主循环：读取 → 检测 → 分类 → 更新
├── tests/
│   ├── conftest.py            # Pytest fixtures 和 MediaPipe 测试图片辅助函数
│   ├── test_camera.py         # CameraSource 测试
│   ├── test_detector.py       # HeadPoseDetector 测试及旋转矩阵欧拉角测试
│   └── test_classifier.py     # PoseClassifier 单元测试和参数化测试
├── docs/
│   └── adr/                   # 架构决策记录
├── main.py                     # 命令行入口：解析 [camera_index]，启动 AppController
└── pyproject.toml
```

### 模块职责

| 模块              | 职责说明                                                                        |
| --------------- | ------------------------------------------------------------------------------- |
| `camera.py`       | 负责打开/重试/释放 `cv2.VideoCapture`。由调用方通过 `retry_open()` 驱动重新连接。      |
| `detector.py`     | 封装 MediaPipe `FaceLandmarker`（VIDEO 模式）。返回 `Optional[(yaw_deg, roll_deg)]`。无人脸时返回 `None`。所有调用方必须遵循文档中的符号约定。 |
| `classifier.py`   | 纯函数 `classify(yaw, roll, neutral, thresholds) → PoseState`。无状态，无副作用。包含 `PoseState` 枚举、`NeutralPose` 和 `Thresholds` 数据类。 |
| `main_window.py`  | PySide6 `QMainWindow`。持有 `CameraSource` 和 `HeadPoseDetector`。负责显示画面、读数和徽章。窗口关闭时清理资源。 |
| `controller.py`   | 持有 10 Hz 的 `QTimer`。每次 tick 调用：读取摄像头 → 检测 → 分类 → 更新窗口。连接 `aboutToQuit` 信号停止计时器。 |

### 数据流

```text
摄像头画面 (BGR, uint8)
  → CameraSource.read()
  → HeadPoseDetector.detect(frame)
    → MediaPipe FaceLandmarker (视频模式)
    → 4×4 变换矩阵 → 3×3 旋转矩阵
    → atan2(R[1,0], R[0,0]) → yaw_deg
    → atan2(R[2,1], R[2,2]) → roll_deg
    → Optional[(yaw_deg, roll_deg)]
  → PoseClassifier.classify(yaw, roll)
    → 与 NeutralPose + Thresholds 比较
    → PoseState（五种状态之一）
  → MainWindow.set_state(yaw, roll, state)
    → 更新角度读数标签
    → 更新徽章颜色和文字
  → MainWindow.update_frame(frame)
    → BGR → RGB → QImage → QPixmap
    → 显示在视频标签上
```

主循环运行频率为 10 Hz（每 100 毫秒一次）。

### 状态机

```text
┌─────────────────┐
│  NO_FACE        │ ← 当前帧中没有人脸
└────────┬────────┘
         │ 检测到人脸
         ▼
┌─────────────────────────────────┐
│  FACING_SCREEN                   │ ← |yaw_dev| ≤ yaw_threshold 且 |roll_dev| ≤ roll_threshold
│  (neutral.yaw=0, neutral.roll=0) │
└────────┬────────────────────────┘
         │ |yaw_dev| > yaw_threshold
         ▼
┌─────────────────────────────────┐
│  OFF_AXIS_LEFT  ← yaw_dev < 0   │ ← 头部向左转（用户自己的左边）
│  OFF_AXIS_RIGHT ← yaw_dev > 0   │ ← 头部向右转（用户自己的右边）
└─────────────────────────────────┘
         │
         │ |yaw_dev| ≤ yaw_threshold 但 |roll_dev| > roll_threshold
         ▼
┌─────────────────────────────────┐
│  OFF_AXIS_OTHER                 │ ← 仅翻滚角偏离（头部歪向肩膀）
└─────────────────────────────────┘
```

注意：当偏航角和翻滚角同时超出阈值时，OFF_AXIS_LEFT 和 OFF_AXIS_RIGHT 优先于 OFF_AXIS_OTHER。

### 计时器与提醒

| 计时器                    | 触发条件                    | 重置条件                  | 行为说明                                                                              |
| ----------------------- | ------------------------- | ---------------------- | ----------------------------------------------------------------------------------- |
| **正对屏幕时间累计器**        | 处于 `FACING_SCREEN` 状态      | 达到 300 秒并发出提醒后重置    | 累计正对屏幕 300 秒后 → 显示"良好"表扬。离开正对屏幕状态时暂停。                                |
| **偏离屏幕连续计时**          | 处于 `OFF_AXIS_LEFT` 或 `OFF_AXIS_RIGHT` | 恢复到 `FACING_SCREEN` 或变成 `NO_FACE` 时重置 | 首次偏离 5 秒后发出调整提醒，之后每 30 秒重复一次。                                              |

### 架构决策记录（ADR）

- **ADR-0001** - 仅检测偏航角和翻滚角，不检测俯仰角和视线。理由：俯仰角在低头看键盘、纸张、手机时容易误报；视线追踪超出 v1 范围。
- **ADR-0002** - 使用累计时间而非挂钟时间。理由：需求中的"每 5 分钟"指的是累计会话时长，而非固定时间间隔。
- **ADR-0003** - 使用 MediaPipe 检测头部姿态。理由：经过充分测试、预训练模型、CPU 运行、准确率和延迟平衡良好。
- **ADR-0004** - 使用自定义浮动窗口而非系统通知。理由：系统原生通知对频繁提醒来说过于打扰；自定义浮窗可以控制外观和防抖逻辑。

## 开发

### 环境搭建

```bash
# 创建并激活虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# 安装包含开发依赖的版本
pip install -e ".[dev]"
```

### 运行测试

```bash
pytest
pytest --cov=src --cov-report=term-missing
```

### 代码质量检查

```bash
ruff check src/
```

### Pre-commit

尚未配置。参见 `AGENTS.md` 了解项目规范。

## 常见问题

### 摄像头无法识别

如果摄像头打开失败，应用会在读数标签上显示提示信息。请尝试：

- 拔掉摄像头数据线后重新插上
- 尝试不同的摄像头索引：`python -m eyes 1`
- 关闭其他可能占用摄像头的应用（Zoom、Teams 等）

### 检测不到人脸

- 请确保面部可见、光线充足
- 请确保摄像头正对或略微俯视你的面部
- MediaPipe 模型在约 2 米范围内效果最佳

### 模型下载失败

首次运行时，MediaPipe 会自动下载人脸特征点模型。如果下载失败，应用会每次运行时自动重试手动下载。如果需要手动下载，模型地址记录在 `src/eyes/detector.py` 中。

### "请向右调整" / "请向左调整" 一直出现

可能需要重新校准中立姿态。保持放松的正对屏幕姿势 5 秒。如果你习惯以某个角度坐着，重新校准可以设定更准确的基准。

### 阈值感觉太严格 / 太宽松

请编辑 `src/eyes/classifier.py`，调整 `Thresholds.yaw_deg` 和 `Thresholds.roll_deg` 的数值。后续版本会通过配置文件或界面滑块来调整这些参数。

## 开源协议

MIT License。详见 [LICENSE](LICENSE)。
