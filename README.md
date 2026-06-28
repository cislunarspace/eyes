<div align="center">

# 👁️ Eyes

**桌面坐姿监测与护眼提醒工具**

[![Rust](https://img.shields.io/badge/Rust-2021-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Tauri 2](https://img.shields.io/badge/Tauri-2-FFC131?logo=tauri&logoColor=white)](https://tauri.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*通过摄像头实时监测头部姿态，提示你保持正确坐姿、适时休息。*

[English](#features) · [中文文档](README_zh.md)

</div>

---

## 功能特性

- **实时头部姿态检测** — YuNet ONNX 模型检测人脸关键点，solvePnP 计算偏航角和俯仰角
- **姿态状态分类** — 正对屏幕、左偏、右偏、抬头、低头、无人脸
- **中性姿态校准** — 保持放松的正对姿势 5 秒，设定个人基准
- **可配置阈值** — 通过设置页面调整偏航和俯仰容差
- **系统托盘** — 后台运行，关闭窗口即最小化到托盘
- **静默模式** — 通过托盘菜单暂停提醒 30 分钟、1 小时或手动恢复
- **坐姿表扬** — 累计正对屏幕 5 分钟后给予鼓励提示
- **护眼提醒** — 累计检测到人脸 15 分钟后提醒远眺
- **阶梯式纠正** — 偏离一定时间后首次提示，之后定时重复
- **摄像头重试** — 摄像头不可用时每 5 秒自动重试
- **开机自启** — 可选随系统启动（Windows 用户级）

## 安装

### Windows MSI 安装程序

从 [Releases](https://github.com/cislunarspace/eyes/releases) 下载最新的 `.msi` 安装包，双击安装。

安装后从开始菜单启动 **Eyes**。

> 安装程序包含所有运行时依赖（OpenCV、ONNX Runtime、ONNX 模型），无需额外安装。

### 从源码构建

```bash
git clone https://github.com/cislunarspace/eyes.git
cd eyes

# 安装前端依赖
npm install

# 开发模式（热重载前端 + Rust 后端）
npm run tauri dev

# 构建 MSI 安装包（需要 OpenCV 和 ONNX Runtime 环境变量）
scripts\build-windows.cmd
```

从源码构建需要：

| 依赖 | 说明 |
|------|------|
| Rust | 1.80+ |
| Node.js | 18+ |
| OpenCV | 4.x，设置 `OPENCV_LINK_PATHS` |
| ONNX Runtime | 1.x，设置 `ORT_LIB_LOCATION` 和 `ORT_STRATEGY=system` |

---

## 使用说明

应用启动后在系统托盘运行，通过摄像头检测你的头部姿态。

### 系统托盘

关闭窗口不会退出应用，而是最小化到系统托盘。

**托盘菜单：**

- **静默 30 分钟** / **静默 1 小时** / **无限静默** — 暂停提醒
- **恢复** — 提前结束静默
- **设置** — 打开设置页面
- **退出** — 完全退出应用

### 中性姿态校准

面对屏幕保持放松姿势 5 秒，应用自动检测并记录你的个人基准。也可以在**设置**里点击**校准**按钮。

---

## 设置

通过托盘菜单打开设置。

| 设置项 | 说明 |
|--------|------|
| 偏航阈值 | 转头容差（度）。超出即判定偏转。 |
| 俯仰阈值 | 抬头/低头容差（度）。超出即判定偏离。 |
| 摄像头 | 选择使用的摄像头（0 = 默认）。 |
| 语言 | 中文 / English |
| 开机自启 | 随系统启动（Windows 用户级）。 |

---

## 配置与日志

配置保存在用户数据目录：

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%\eyes\config.yaml` |
| macOS | `~/Library/Application Support/eyes/config.yaml` |
| Linux | `~/.config/eyes/config.yaml` |

事件日志（JSONL 格式）也写入同一目录。

卸载应用时用户配置保留，不会被删除。

---

## 架构

```text
src-tauri/                   Rust 后端 (Tauri 2)
├── src/
│   ├── lib.rs               应用入口、Tauri Builder 配置
│   ├── app_state.rs         共享状态容器
│   ├── commands.rs          Tauri commands + 后台 worker
│   ├── app_shell/           托盘、窗口、事件
│   ├── domain/              纯领域逻辑（分类、计时、校准、配置）
│   └── monitoring/          摄像头、检测器、worker
└── tests/                   行为测试

src/                         React + TypeScript 前端
models/                      ONNX 模型文件
docs/                        ADR、PRD、迁移计划
```

### 数据流

```text
摄像头帧 (RGB)
  → OpenCvCamera.read_frame()
  → YuNetDetector.detect(rgb, w, h)
    → 人脸关键点 → solvePnP → HeadPose(yaw, pitch)
  → classifier::classify(pose, config)
    → PoseState (FacingScreen / OffAxisLeft / ...)
  → PostureTickEngine.tick(yaw_state, pitch_state, dt)
    → 计时器推进 → 生成 SenseEvent 列表
  → 前端事件 (pose-updated / correction / good-posture / eye-rest)
```

循环频率约 10 Hz（每 tick 100ms）。

---

## 开发

```bash
# 安装依赖
npm install

# 开发模式
npm run tauri dev

# 运行 Rust 测试（不需要 OpenCV/ONNX）
cd src-tauri && cargo test --no-default-features

# 代码检查
cd src-tauri && cargo clippy --no-default-features
```

---

## 常见问题

### 关闭窗口后应用还在运行

预期行为。关闭窗口最小化到系统托盘。要完全退出，点击托盘菜单的**退出**。

### 摄像头被其他应用占用

应用每 5 秒自动重试。关闭占用摄像头的应用（Zoom、Teams 等）后自动恢复。

### 阈值太严 / 太松

从托盘菜单打开**设置**，调整阈值。

### 卸载后配置还在吗？

是的。卸载只删除应用文件，用户配置保留在 `%APPDATA%\eyes\`。如需清除，手动删除该目录。

## 许可证

MIT License，详见 [LICENSE](LICENSE)。
