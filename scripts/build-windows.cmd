@echo off
setlocal enabledelayedexpansion
REM Windows 打包脚本（M7）
REM
REM 前提条件：
REM   1. 设置 OPENCV_LINK_PATHS 指向 OpenCV DLL 所在目录
REM      例如：set OPENCV_LINK_PATHS=C:\opencv\build\x64\vc16\bin
REM   2. 设置 ORT_LIB_LOCATION 指向 ONNX Runtime DLL 所在目录
REM      例如：set ORT_LIB_LOCATION=C:\onnxruntime\lib
REM   3. 设置 ORT_STRATEGY=system 让 ort crate 链接系统库而非下载
REM
REM 用法：
REM   scripts\build-windows.cmd

set ORT_STRATEGY=system

if not defined OPENCV_LINK_PATHS (
    echo [错误] 未设置 OPENCV_LINK_PATHS
    echo   示例：set OPENCV_LINK_PATHS=C:\opencv\build\x64\vc16\bin
    exit /b 1
)

if not defined ORT_LIB_LOCATION (
    echo [错误] 未设置 ORT_LIB_LOCATION
    echo   示例：set ORT_LIB_LOCATION=C:\onnxruntime\lib
    exit /b 1
)

if not exist "models\face_detection_yunet_2023mar.onnx" (
    echo [错误] 模型文件不存在：models\face_detection_yunet_2023mar.onnx
    exit /b 1
)

echo === 构建 Eyes Windows 安装程序 ===
echo OPENCV_LINK_PATHS=%OPENCV_LINK_PATHS%
echo ORT_LIB_LOCATION=%ORT_LIB_LOCATION%
echo.

npx tauri build
if !errorlevel! neq 0 (
    echo.
    echo === 构建失败 ===
    exit /b 1
)

REM 验证 DLL 已被真实文件替换（非占位空文件）
for %%F in (src-tauri\onnxruntime.dll) do (
    if %%~zF==0 (
        echo [警告] onnxruntime.dll 是空文件，DLL 可能未正确打包
    )
)

echo.
echo === 构建完成 ===
echo MSI 安装程序位于 src-tauri\target\release\bundle\msi\
