# Changelog

## [0.2.0] — 2026-06-27

### Rust/Tauri 重写

Python 版本的完整 Rust 移植，使用 Tauri 2 构建桌面壳。

**新增：**

- Tauri 2 桌面壳：系统托盘、关闭时最小化、单实例锁
- Domain 层纯逻辑：校准、姿态分类、时间累积、显示计划、事件日志、静默
- 摄像头预览：OpenCV 捕获 → RGB → PNG data URL → 前端
- 后台 worker 线程，~10 Hz tick，5 秒摄像头重试
- 共享状态容器（AppState），Tauri commands 暴露给前端
- Detector trait（M4 ONNX 实现待接入）
- 42 个 Rust 行为测试，cargo clippy 零警告

**保留：**

- 全部 Python 代码和测试仍可用，未删除
- 配置格式（YAML）、事件日志格式（JSONL）兼容 Python 版

## [0.1.0] — 2025-xx-xx

初始 Python 版本：摄像头监测、姿态分类、坐姿提示、休息提醒。
