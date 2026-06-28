# Changelog

## [0.3.0] — 2026-06-28

### M7 — Windows 打包

- Tauri 构建流水线产出 MSI 安装包
- ONNX Runtime 和 OpenCV DLL 随安装包分发
- ONNX 模型文件通过 bundle.resources 打包
- `build-windows.cmd` 构建辅助脚本
- `models/MANIFEST.toml` 模型溯源清单

### M8 — 旧代码清理

- 删除全部 Python 源码、测试、PyInstaller 规格、构建脚本
- 删除 Python CI 流水线（`.github/workflows/linux-build.yml`）
- 删除 `pyproject.toml`、`uv.lock`、`.python-version`
- 旧 README 存档至 `docs/legacy/`
- 新 README 描述 Rust/Tauri 应用、Windows 安装流程、配置路径、卸载策略

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

## [0.1.0] — 2025-xx-xx

初始 Python 版本：摄像头监测、姿态分类、坐姿提示、休息提醒。
