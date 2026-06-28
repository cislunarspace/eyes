<div align="center">

# 👁️ Eyes 护眼助手

**桌面坐姿监测与护眼提醒工具**

[![Rust](https://img.shields.io/badge/Rust-2021-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Tauri 2](https://img.shields.io/badge/Tauri-2-FFC131?logo=tauri&logoColor=white)](https://tauri.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*通过摄像头实时监测头部姿态，提醒你保持正确坐姿、适时休息。*

[English](README.md) · [中文文档](#功能特点)

</div>

---

## 功能特点

- **实时头部姿态检测** — YuNet ONNX 模型检测人脸关键点，solvePnP 计算头部姿态
- **偏航角和俯仰角追踪** — 偏航角（左右转头）和俯仰角（抬头低头）独立追踪
- **姿态状态分类** — 正对屏幕、左偏、右偏、抬头、低头、无人脸
- **中性姿态校准** — 保持放松的正对屏幕姿势 5 秒，设定个人基准
- **阈值可调节** — 通过设置界面调整偏航和俯仰的容忍范围
- **系统托盘** — 关闭窗口后最小化到托盘，后台运行
- **暂停功能** — 通过托盘菜单暂停提醒 30 分钟、1 小时或手动恢复
- **定时姿态表扬** — 累计正对屏幕 5 分钟，给予正向反馈
- **护眼提醒** — 累计检测到人脸 15 分钟后提醒远眺
- **阶梯式纠正** — 偏离一定时间后首次提示，之后定时重复提醒
- **开机自启** — 可选随系统启动（Windows 用户级）

## 安装

### Windows 安装包

从 [Releases](https://github.com/cislunarspace/eyes/releases) 下载 `.msi` 安装包，双击安装。从开始菜单启动。

安装包已包含所有运行时组件（OpenCV、ONNX Runtime、检测模型），无需额外安装。

### 从源码构建

```bash
git clone https://github.com/cislunarspace/eyes.git
cd eyes
npm install
npm run tauri dev       # 开发模式
scripts\build-windows.cmd  # 构建 MSI
```

构建需要 Rust 1.80+、Node.js 18+、OpenCV 4.x、ONNX Runtime 1.x。

---

## 使用说明

应用启动后在系统托盘运行，通过摄像头持续检测头部姿态。

### 系统托盘菜单

- **静默 30 分钟 / 1 小时 / 无限静默** — 暂停所有提醒
- **恢复** — 提前结束静默
- **设置** — 打开设置页面
- **退出** — 完全退出应用

### 中性姿态校准

面对屏幕保持放松姿势 5 秒，应用自动记录你的个人基准。也可在设置中手动触发校准。

---

## 设置

| 设置项 | 说明 |
|--------|------|
| 偏航阈值 | 转头容差（度） |
| 俯仰阈值 | 抬头/低头容差（度） |
| 摄像头 | 选择摄像头设备 |
| 语言 | 中文 / English |
| 开机自启 | 随 Windows 启动 |

## 配置文件路径

| 平台 | 路径 |
|------|------|
| Windows | `%APPDATA%\eyes\config.yaml` |
| macOS | `~/Library/Application Support/eyes/config.yaml` |
| Linux | `~/.config/eyes/config.yaml` |

卸载应用时配置文件保留。如需清除，手动删除上述目录。

---

## 项目结构

```
src-tauri/          Rust 后端（Tauri 2）
src/                React + TypeScript 前端
models/             ONNX 模型文件
docs/               架构决策记录、产品文档
```

## 许可证

MIT License。
