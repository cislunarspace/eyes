# Eyes 护眼助手

一款桌面应用，用摄像头实时监测你的头部姿态，在你偏离屏幕方向时提醒你调整，或定时提示你让眼睛休息一下。

---

## 功能特点

- **实时头部姿态检测** - 调用 MediaPipe FaceLandmarker，利用摄像头捕捉画面
- **偏航角和翻滚角追踪** - 偏航角（左右转头）和翻滚角（头部倾斜）实时显示
- **姿态状态分类** - 分为：正对屏幕、偏左、偏右、其他偏离、无检测到人脸
- **中立姿态校准** - 保持放松的正对屏幕姿势 5 秒，即可设为个人基准
- **阈值可调节** - 通过设置界面调整偏航角和翻滚角的容忍范围
- **系统托盘** - 关闭窗口后最小化到托盘，后台运行
- **暂停功能** - 通过托盘菜单暂停提醒 30 分钟、1 小时或手动恢复
- **定时姿态表扬** - 累计正对屏幕时长达到 300 秒时，提示"良好"给予正向反馈
- **眺望远方提醒** - 累计检测到人脸时长达到 900 秒时，提示让眼睛休息
- **防抖提醒机制** - 偏离屏幕 5 秒后首次提醒，之后每 30 秒重复提醒
- **设置界面** - 图形化配置阈值、校准、摄像头选择、提示音、开机自启
- **持久化配置** - 设置保存到 `~/.config/eyes/config.yaml`
- **摄像头自动重试** - 摄像头被占用时每 5 秒自动重试
- **开机自启** - 可选开机自动启动
- **PySide6 图形界面** - 实时摄像头预览、彩色状态徽章、角度数值显示

---

## 系统要求

- **操作系统**：Windows、macOS 或 Linux
- **Python**：3.12 或更高版本
- **摄像头**：任意可被 OpenCV 访问的摄像头（默认为摄像头索引 0）
- **依赖库**：MediaPipe、OpenCV、PySide6（随安装自动安装）

---

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

---

## 使用方法

```bash
python main.py
python main.py 0          # 显式指定默认摄像头
python main.py 1          # 使用第二个摄像头
```

启动后，窗口会显示：

- **实时摄像头预览** - 你的摄像头画面
- **彩色徽章** - 当前姿态状态（绿色 = 正对屏幕，红色 = 偏离，橙色 = 仅翻滚角偏离，灰色 = 未检测到人脸）
- **角度数值** - 实时的偏航角和翻滚角（单位：度，如 `yaw: -3.2°   roll: +1.1°`）

### 系统托盘

关闭窗口后，应用会最小化到系统托盘而不是退出。托盘图标显示当前状态：

| 图标 | 状态 | 说明 |
| ---- | ---- | ---- |
| 绿色 | 活跃 (Active) | 应用正在运行和监测 |
| 黄色 | 已暂停 (Paused) | 暂停功能已启用 |
| 灰色 | 不可用 (Unavailable) | 摄像头不可用 |

**托盘菜单选项：**

- **暂停 30 分钟** - 暂停提醒 30 分钟
- **暂停 1 小时** - 暂停提醒 1 小时
- **暂停直到我恢复** - 无限期暂停，直到手动恢复
- **恢复** - 恢复监测（仅在暂停时可用）
- **打开设置** - 打开设置界面
- **退出** - 完全退出应用

暂停设置会在重启后保留。

### 中立姿态校准

运行应用时，保持放松的正对屏幕姿势 5 秒。应用会自动检测并记录这个稳定的前方姿势，作为后续所有偏离判断的基准。这样无论你相对摄像头的坐姿角度如何，应用都能准确工作。

也可以在设置界面中点击 **校准中立姿态** 按钮进行校准。

---

## 设置

通过托盘菜单中的 **打开设置** 打开设置界面。

| 设置项 | 说明 |
| ------ | ---- |
| 偏航阈值 | 偏航角容忍范围，5-30°。超出此阈值判定为偏离。 |
| 翻滚阈值 | 翻滚角容忍范围，5-30°。超出此阈值判定为翻滚角偏离。 |
| 中立姿态 | 当前校准的基准姿态。点击 **校准中立姿态** 可重新校准（保持正对 5 秒）。 |
| 摄像头 | 选择使用的摄像头（0 = 默认摄像头）。 |
| 提示音 | 开关提示音。 |
| 开机自启 | 开关开机自动启动。 |

---

## 配置

设置会持久化保存到 `~/.config/eyes/config.yaml`（通过 [platformdirs](https://pypi.org/project/platformdirs/)）。你可以直接编辑此文件，也可以使用设置界面。

### 配置项说明

```yaml
yaw_threshold: 15.0        # 偏航角容忍范围（度）
roll_threshold: 10.0       # 翻滚角容忍范围（度）
neutral_yaw: 0.0           # 校准后的基准偏航角
neutral_roll: 0.0          # 校准后的基准翻滚角
camera_index: 0            # 使用的摄像头索引
snooze_until_iso: null     # 暂停到期时间（ISO 8601），null=未暂停，"indefinite"=手动恢复
sound_enabled: false       # 是否启用提示音
autostart_enabled: false   # 开机自动启动
language: zh-CN            # UI 语言（目前仅支持中文）
```

---

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
│   ├── classifier.py          # PoseClassifier + NeutralPose + Thresholds + classify()
│   ├── accumulator.py         # AccumulatorEngine - 偏离计时 + S4/S5 计时器
│   ├── overlay.py             # NotifierOverlay - 置顶提醒浮窗
│   ├── config_store.py        # ConfigStore - YAML 配置持久化
│   ├── settings_dialog.py     # SettingsDialog - 阈值、校准、摄像头、提示音、开机自启设置界面
│   ├── tray_controller.py     # TrayController - 系统托盘图标 + 暂停菜单
│   ├── event_log.py           # EventLog - 会话事件记录
│   ├── autostart.py           # AutostartManager - 开机自启管理
│   ├── calibration.py         # PoseSample + compute_median_pose()
│   ├── types.py               # AppConfig + AppEventKind
│   ├── main_window.py         # MainWindow - PySide6 图形界面
│   └── controller.py          # AppController - 10 Hz 主循环
├── tests/                      # pytest 测试
├── docs/
│   └── adr/                   # 架构决策记录
├── main.py                     # 命令行入口
└── pyproject.toml
```

### 模块职责

| 模块 | 职责说明 |
| ---- | -------- |
| `camera.py` | 负责打开/重试/释放 `cv2.VideoCapture`。由调用方通过 `retry_open()` 驱动重新连接。 |
| `detector.py` | 封装 MediaPipe `FaceLandmarker`（VIDEO 模式）。返回 `Optional[HeadPose]`。 |
| `classifier.py` | 纯函数 `classify(pose, neutral, thresholds) → PoseState`。`pose=None` 时返回 `NO_FACE`。 |
| `accumulator.py` | 纯状态机：偏离计时、S4（正对时间）、S5（人脸检测时间）。由外部 dt 驱动。 |
| `overlay.py` | 无边框置顶窗口，用于显示提醒。4 秒后自动消失。 |
| `config_store.py` | 通过临时文件再重命名的原子化 YAML 读写。 |
| `settings_dialog.py` | PySide6 对话框，包含滑块、校准按钮、摄像头选择、开关。 |
| `tray_controller.py` | `QSystemTrayIcon`，包含暂停/恢复/设置/退出菜单。 |
| `event_log.py` | 会话事件记录器（状态变化、提醒、摄像头事件、暂停）。 |
| `autostart.py` | 操作系统特定的开机自启注册/移除。 |
| `calibration.py` | `compute_median_pose()` - 计算姿态样本的中位数。 |
| `types.py` | `AppConfig`（不可变数据类），`AppEventKind`（枚举）。 |
| `main_window.py` | `QMainWindow`。持有 `CameraSource` 和 `HeadPoseDetector`。窗口关闭时清理资源。 |
| `controller.py` | 持有 10 Hz 的 `QTimer`。每次 tick 调用：读取 → 检测 → 分类 → 累计 → 更新窗口。 |

### 数据流

```text
摄像头画面 (BGR, uint8)
  → CameraSource.read()
  → HeadPoseDetector.detect(frame)
    → MediaPipe FaceLandmarker (视频模式)
    → 4×4 变换矩阵 → 3×3 旋转矩阵 → 欧拉角
    → Optional[HeadPose(yaw, roll)]
  → PoseClassifier.classify(pose, neutral, thresholds)
    → 与 NeutralPose + Thresholds 比较
    → PoseState（五种状态之一）
  → AccumulatorEngine.tick(state, dt)
    → 追踪偏离计时 → 符合条件时触发提醒
    → 追踪 S4/S5 计时器 → 符合条件时触发表扬/眼休
  → MainWindow.set_state(yaw, roll, state)
    → 更新角度读数标签
    → 更新徽章颜色和文字
  → MainWindow.update_frame(frame)
    → BGR → RGB → QImage → QPixmap
    → 显示在视频标签上
  → NotifierOverlay（AccumulatorEngine 触发时）
    → 显示置顶调整提醒
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
│  (neutral.yaw, neutral.roll)    │
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

| 计时器 | 触发条件 | 重置条件 | 行为说明 |
| ------- | -------- | -------- | -------- |
| **偏离屏幕连续计时** | 处于 `OFF_AXIS_LEFT` 或 `OFF_AXIS_RIGHT` | 恢复到 `FACING_SCREEN` 或变成 `NO_FACE` | 首次偏离 5 秒后发出调整提醒，之后每 30 秒重复一次。 |
| **正对屏幕时间累计器 (S4)** | 处于 `FACING_SCREEN` | 短暂偏离不会重置，只会暂停 | 累计正对屏幕 300 秒后 → 显示表扬提醒，重置为 0 重新开始。 |
| **人脸检测时间累计器 (S5)** | 检测到任何人脸状态（非 NO_FACE） | NO_FACE 时暂停但不会重置 | 累计 900 秒后 → 显示"请眺望远方"眼休提醒，重置为 0 重新开始。 |

**暂停行为：** 暂停期间，所有计时器和累计器冻结在当前值（不前进也不后退）。恢复后会从冻结的位置继续。

### 架构决策记录（ADR）

详见 `docs/adr/` 目录：

- **ADR-0001** - 仅检测偏航角和翻滚角，不检测俯仰角和视线。
- **ADR-0002** - 使用累计时间而非挂钟时间。
- **ADR-0003** - 使用 MediaPipe 检测头部姿态。
- **ADR-0004** - 使用自定义浮动窗口而非系统通知。

---

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

---

## 常见问题

### 关闭窗口后应用仍在运行

这是正常行为。关闭窗口会将应用最小化到系统托盘。如需完全退出，请点击托盘菜单中的 **退出**。

### 摄像头被其他程序占用

应用会每 5 秒自动重试一次。重试期间托盘图标显示为灰色，窗口中会显示"摄像头被其他程序占用…等待恢复"。关闭占用摄像头的应用（如 Zoom、Teams 等），应用会自动恢复。

### "请向右调整" / "请向左调整" 一直出现

你需要重新校准中立姿态。面向屏幕保持放松的坐姿 5 秒，或在 **打开设置** → **校准中立姿态** 中重新校准。如果自然坐姿有角度偏差，重新校准会设置更准确的中立基准。

### 阈值感觉太严格 / 太宽松

在托盘菜单中点击 **打开设置**，使用滑块调整 **偏航阈值** 和 **翻滚阈值**。

### 如何使用暂停功能？

点击托盘图标打开菜单，选择 **暂停 30 分钟**、**暂停 1 小时** 或 **暂停直到我恢复**。暂停期间托盘图标显示为黄色，所有提醒和计时器冻结。点击 **恢复** 可手动解除暂停。定时暂停会在到期后自动解除。

### 良好姿势提醒是做什么的？

累计面向屏幕时间达到 300 秒（5 分钟）时，会显示鼓励提示。这不是实时计时，而是在你保持正确姿势时逐渐累加的。

### 眺望远方提醒是做什么的？

累计检测到人脸时间达到 900 秒（15 分钟）时，会显示"请眺望远方"提示，提示你让眼睛休息一下。离开摄像头时计时暂停，但不会重置。

### 检测不到人脸

请确保：

- 面部清晰可见且光照充足
- 摄像头对准你的面部，大致在同一高度
- 距离摄像头在 2 米以内

### 模型下载失败

首次运行时，MediaPipe 会自动下载人脸特征点模型。如果下载失败，应用会每次运行时自动重试。如果需要手动下载，模型地址记录在 `src/eyes/detector.py` 中。

---

## 开源协议

MIT License。详见 [LICENSE](LICENSE)。
