<div align="center">

# 👁️ Eyes

**桌面坐姿监测与护眼提醒工具**

[![Rust](https://img.shields.io/badge/Rust-2021-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Tauri 2](https://img.shields.io/badge/Tauri-2-FFC131?logo=tauri&logoColor=white)](https://tauri.app/)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*通过摄像头实时监测头部姿态，提示你保持正确坐姿、适时休息。*

[English](#features) · [中文文档](README_zh.md)

</div>

---

## 功能特性

- **实时头部姿态检测** — 通过摄像头追踪偏航角（左右转头）和滚转角（头部倾斜）
- **姿态状态分类** — 正对屏幕、左偏、右偏、其他偏转、无人脸
- **中性姿态校准** — 保持放松的正对姿势 5 秒，设定个人基准
- **可配置阈值** — 通过设置对话框调整偏航和滚转容差
- **系统托盘** — 后台运行，关闭窗口即最小化到托盘
- **静默模式** — 通过托盘菜单暂停提醒 30 分钟、1 小时或手动恢复
- **坐姿表扬** — 累计正对屏幕 5 分钟后给予鼓励提示
- **护眼提醒** — 累计检测到人脸 15 分钟后提醒远眺
- **阶梯式纠正** — 偏离 5 秒首次提示，之后每 30 秒重复
- **摄像头重试** — 摄像头不可用时每 5 秒自动重试
- **开机自启** — 可选随系统启动

> 当前处于 Rust/Tauri 重写阶段。Domain 层（校准、分类、计时、事件日志）和摄像头预览已完成。
> 姿态检测（M4）仍使用 Python/MediaPipe，正在接入 ONNX Runtime。

## 环境要求

| 依赖 | 说明 |
|------|------|
| **OS** | Windows、macOS 或 Linux |
| **Rust** | 1.80+（编译 Tauri 后端） |
| **Node.js** | 18+（构建前端） |
| **Python** | 3.12+（姿态检测，M4 完成后移除） |
| **摄像头** | 任意可通过 OpenCV 访问的摄像头（默认索引 0） |

---

## 快速开始

### Rust/Tauri 开发（推荐）

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes

# 安装前端依赖
npm install

# 开发模式运行（热重载前端 + Rust 后端）
npm run tauri dev

# 构建发布包
npm run tauri build
```

### Python 开发（用于姿态检测）

```bash
cd eyes
uv sync
uv run python main.py
```

---

## 使用说明

应用打开后显示：

- **实时摄像头预览** — 你的摄像头画面
- **彩色标签** — 当前姿态状态（绿色 = 正对屏幕，红色 = 偏转，琥珀色 = 滚转偏差，灰色 = 无人脸）
- **角度读数** — 实时偏航角和滚转角（例如 `yaw: -3.2°   roll: +1.1°`）

### 系统托盘

关闭窗口不会退出应用，而是最小化到系统托盘。托盘图标反映当前状态：

| 图标 | 状态 | 说明 |
|------|------|------|
| 🟢 绿色 | 运行中 | 正在监测 |
| 🟡 黄色 | 已暂停 | 静默模式生效 |
| ⚪ 灰色 | 不可用 | 摄像头不可用 |

**托盘菜单：**

- **静默 30 分钟** / **静默 1 小时** / **无限静默** — 暂停提醒
- **恢复** — 提前结束静默
- **设置** — 打开设置对话框
- **退出** — 完全退出应用

### 中性姿态校准

应用运行时保持放松的正对姿势 5 秒，应用会检测到这个稳定位置并作为你的个人基准。也可以在**设置**里点击**校准**按钮。

---

## 设置

通过托盘菜单打开设置。

| 设置项 | 说明 |
|--------|------|
| 偏航阈值 | 转头容差，5–30°。超出即判定偏转。 |
| 滚转阈值 | 头部倾斜容差，5–30°。超出即判定滚转偏差。 |
| 中性姿态 | 当前校准基准。点击**校准**重新设定（保持正对 5 秒）。 |
| 摄像头 | 选择使用的摄像头（0 = 默认）。 |
| 声音 | 开关提示音效。 |
| 开机自启 | 开关系统启动时自动运行。 |

---

## 配置文件

设置保存在 `~/.config/eyes/config.yaml`（Rust 版使用 `dirs::config_dir()`）。可以直接编辑或通过设置对话框修改。

```yaml
yaw_threshold: 15.0        # 偏航容差（度）
roll_threshold: 10.0       # 滚转容差（度）
neutral_yaw: 0.0           # 校准基准偏航
neutral_roll: 0.0          # 校准基准滚转
camera_index: 0            # 摄像头索引
snooze_until_iso: null     # 静默到期时间（ISO 8601），null = 未静默
sound_enabled: false       # 提示音开关
autostart_enabled: false   # 开机自启开关
language: zh-CN            # UI 语言
```

---

## 架构

### 项目结构

```text
eyes/
├── src-tauri/                   # Rust 后端 (Tauri 2)
│   ├── src/
│   │   ├── lib.rs               # 应用入口、Tauri Builder 配置
│   │   ├── app_state.rs         # 共享状态容器
│   │   ├── commands.rs          # Tauri commands + 后台 worker
│   │   ├── app_shell/
│   │   │   ├── contract.rs      # 托盘/窗口决策常量
│   │   │   ├── desktop.rs       # Tauri 原生 API 集成
│   │   │   └── events.rs        # WorkerEvent → Tauri emit
│   │   ├── domain/
│   │   │   ├── calibration.rs   # 校准会话 + 中位数计算
│   │   │   ├── classifier.rs    # 姿态分类纯函数
│   │   │   ├── config.rs        # YAML 配置持久化
│   │   │   ├── display_plan.rs  # 提示内容生成
│   │   │   ├── event_log.rs     # JSONL 事件日志
│   │   │   ├── posture_tick_engine.rs  # 时间累积状态机
│   │   │   └── snooze.rs        # 静默状态评估
│   │   └── monitoring/
│   │       ├── detector.rs      # Detector trait
│   │       ├── preview.rs       # Frame → PNG data URL
│   │       ├── opencv_camera.rs # OpenCV 摄像头实现
│   │       └── worker.rs        # 后台 worker 定义
│   └── tests/                   # 行为测试（42 个）
├── src/eyes/                    # Python 前代代码（仍可用）
├── docs/
│   ├── adr/                     # 架构决策记录
│   └── prd/                     # 产品需求文档
└── workflows/                   # Agent 工作流文档
```

### 数据流

```text
摄像头帧 (RGB)
  → OpenCvCamera.read_frame()
  → Detector.detect(rgb, width, height)        # M4 ONNX 待接入
    → Option<HeadPose(yaw, roll)>
  → PostureTickEngine.on_pose(pose, now)
    → classify → 映射到 PoseState
    → 计时器推进 → 生成提示列表
    → 更新 SnoozeState
  → DisplayPlan::from_pose_state(pose, warning, snooze)
    → 生成 UI 提示内容
  → emit_worker_event() → 前端
```

循环频率约 10 Hz（每 tick 100ms）。

### 状态机

```text
┌─────────────────┐
│  NoFace         │ ← 画面中无人脸
└────────┬────────┘
         │ 检测到人脸
         ▼
┌─────────────────────────────────┐
│  FacingScreen                   │ ← |偏航偏差| ≤ 偏航阈值 且 |滚转偏差| ≤ 滚转阈值
└────────┬────────────────────────┘
         │ |偏航偏差| > 偏航阈值
         ▼
┌─────────────────────────────────┐
│  OffAxisLeft  ← 偏差 < 0        │ ← 头转向用户左侧
│  OffAxisRight ← 偏差 > 0        │ ← 头转向用户右侧
└─────────────────────────────────┘
         │
         │ |偏航偏差| ≤ 偏航阈值 但 |滚转偏差| > 滚转阈值
         ▼
┌─────────────────────────────────┐
│  OffAxisOther                   │ ← 仅滚转偏差（头歪向肩膀）
└─────────────────────────────────┘
```

当偏航和滚转同时超阈值时，OffAxisLeft/Right 优先于 OffAxisOther。

### 计时器与提示

| 计时器 | 触发条件 | 重置条件 | 行为 |
|--------|----------|----------|------|
| **偏转连续计时** | OffAxisLeft 或 OffAxisRight | 回到 FacingScreen 或 NoFace | 5 秒首次纠正提示，之后每 30 秒重复 |
| **正对时间 (S4)** | FacingScreen | 短暂偏离不重置，仅暂停 | 累计 300 秒 → 表扬提示。触发后归零 |
| **在场时间 (S5)** | 任一检测到人脸的状态 | NoFace 不重置，仅暂停 | 累计 900 秒 → 护眼提醒。触发后归零 |

**静默行为：** 静默生效时所有计时器冻结，不前进也不后退。恢复后从冻结点继续。

### 设计决策 (ADR)

详见 `docs/adr/`：

- **ADR-0001** — 只检测偏航和滚转，忽略俯仰和眼动
- **ADR-0002** — 累计时间计时器（不用挂钟时间）
- **ADR-0003** — 使用 MediaPipe 做头部姿态检测
- **ADR-0004** — 自定义浮动窗口替代系统通知
- **ADR-0005** — Rust 重写方向

---

## 开发

### 环境搭建

```bash
# Rust 后端
rustup default stable

# 前端
npm install

# Python（姿态检测，可选）
uv sync --extra dev
```

### 运行测试

```bash
# Rust 行为测试
cd src-tauri && cargo test

# Python 测试
pytest
```

### 代码检查

```bash
cd src-tauri && cargo clippy
```

---

## 常见问题

### 关闭窗口后应用还在运行

这是预期行为。关闭窗口会最小化到系统托盘。要完全退出，点击托盘菜单的**退出**。

### 摄像头被其他应用占用

应用每 5 秒自动重试，托盘图标变为灰色。关闭占用摄像头的应用（Zoom、Teams 等）后会自动恢复。

### 纠正提示一直出现

需要重新校准中性姿态。面对屏幕保持放松姿势 5 秒，或在**设置**里点击**校准**。

### 阈值太严 / 太松

从托盘菜单打开**设置**，调整**偏航阈值**和**滚转阈值**滑块。

### 静默模式如何工作？

点击托盘图标，选择**静默 30 分钟**、**静默 1 小时**或**无限静默**。静默期间托盘图标变黄，所有计时器冻结。点击**恢复**提前结束。定时静默会自动到期。

### 坐姿表扬是什么？

累计正对屏幕 300 秒（5 分钟）后显示鼓励提示。目光移开时计时暂停（不归零）。

### 护眼提醒是什么？

累计检测到人脸 900 秒（15 分钟）后显示远眺提醒。离开摄像头时计时暂停（不归零）。

### 检测不到人脸

确认：

- 脸部清晰可见，光线充足
- 摄像头对准脸部，大致与脸同高
- 距摄像头 2 米以内

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
