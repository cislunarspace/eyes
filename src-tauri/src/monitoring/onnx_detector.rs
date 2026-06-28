//! ONNX 检测器 spike 评估脚手架。
//!
//! 这个模块提供 `YuNetPfplDetector` 的骨架实现，用于 M4a spike。
//! 当前代码是伪实现——需要填充真实的模型加载和推理逻辑。
//!
//! # 使用方法
//!
//! 1. 将 YuNet 和 PFLD 的 ONNX 模型文件放到 `models/` 目录
//! 2. 在 Cargo.toml 中添加 `ort = "2"` 依赖
//! 3. 运行 `cargo test --test onnx_detector_spike -- --nocapture` 查看延迟数据
//! 4. 用摄像头运行手动测试验证 5 种姿态

use crate::domain::classifier::HeadPose;
use crate::monitoring::detector::Detector;

/// YuNet + PFLD + solvePnP 两阶段检测器。
///
/// 工作流程：
/// 1. YuNet 检测人脸边界框
/// 2. PFLD 在裁剪区域定位 98/106 个 2D 关键点
/// 3. OpenCV solvePnP 计算 3D 旋转
/// 4. 从旋转矩阵提取 yaw 和 pitch
pub struct YuNetPfplDetector {
    // TODO: ort session fields
    // yunet_session: ort::Session,
    // pfld_session: ort::Session,
}

impl YuNetPfplDetector {
    /// 从模型文件路径创建检测器。
    ///
    /// # Arguments
    /// * `yunet_path` - YuNet ONNX 模型文件路径
    /// * `pfld_path` - PFLD ONNX 模型文件路径
    pub fn new(_yunet_path: &str, _pfld_path: &str) -> Result<Self, String> {
        // TODO: 实现模型加载
        // 1. 创建 ort::Environment
        // 2. 加载 YuNet session
        // 3. 加载 PFLD session
        // 4. 验证输入输出 shape
        Err("Not implemented — fill in during spike".to_string())
    }
}

impl Detector for YuNetPfplDetector {
    fn detect(&mut self, _rgb: &[u8], _width: u32, _height: u32) -> Option<HeadPose> {
        // TODO: 实现推理流程
        //
        // Step 1: 预处理
        //   - 将 rgb buffer 转为 YuNet 输入格式 (NCHW, float32, normalized)
        //
        // Step 2: YuNet 人脸检测
        //   - 输入: 预处理后的图像
        //   - 输出: 人脸边界框 [x, y, w, h] + confidence
        //   - 如果 confidence < threshold，返回 None
        //
        // Step 3: 裁剪人脸区域
        //   - 根据边界框裁剪 RGB 图像
        //   - 缩放到 PFLD 输入尺寸
        //
        // Step 4: PFLD 关键点检测
        //   - 输入: 裁剪后的人脸图像
        //   - 输出: 98/106 个 2D 关键点 [(x, y), ...]
        //
        // Step 5: solvePnP 计算旋转
        //   - 使用 2D 关键点 + 3D 模型点
        //   - 调用 OpenCV solvePnP 得到旋转向量
        //   - 转换为旋转矩阵
        //
        // Step 6: 提取 yaw 和 pitch
        //   - 从旋转矩阵的 (0,2)/(2,2) 提取 yaw
        //   - 从旋转矩阵的 (1,0)/(1,1) 提取 pitch
        //   - 转换为度数
        //
        // 注意符号约定：
        //   - positive yaw = 头转向用户右侧
        //   - positive pitch = 仰头

        None
    }
}

/// 3D 关键点模型点（用于 solvePnP）。
///
/// 这是标准的 6 点 3D 模型，对应人脸的关键位置：
/// - 鼻尖
/// - 下巴
/// - 左眼外角
/// - 右眼外角
/// - 左嘴角
/// - 右嘴角
///
/// 如果使用 PFLD 的 98/106 关键点，需要选择合适的子集映射到这些 3D 点。
pub const FACE_MODEL_POINTS_3D: &[[f64; 3]] = &[
    [0.0, 0.0, 0.0],           // 鼻尖
    [0.0, -63.6, -12.5],       // 下巴
    [-43.3, 32.7, -26.0],      // 左眼外角
    [43.3, 32.7, -26.0],       // 右眼外角
    [-28.9, -28.9, -24.1],     // 左嘴角
    [28.9, -28.9, -24.1],      // 右嘴角
];

/// 从旋转矩阵提取 yaw 和 pitch（度数）。
///
/// 复用 Python 版 `head_pose_geometry.rotation_to_yaw_roll` 的逻辑。
/// pitch 的提取需要根据 PFLD 关键点的排列方式调整。
pub fn rotation_to_yaw_pitch(rotation: &[[f64; 3]; 3]) -> (f64, f64) {
    let yaw = rotation[0][2].atan2(rotation[2][2]);
    // TODO: pitch 的提取取决于关键点排列，需要 spike 时验证
    // 这里用 rotation[1][0] 和 rotation[1][1] 作为初始值
    let pitch = rotation[1][0].atan2(rotation[1][1]);
    (yaw.to_degrees(), pitch.to_degrees())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rotation_to_yaw_pitch_identity_gives_zero() {
        let identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
        let (yaw, pitch) = rotation_to_yaw_pitch(&identity);
        assert!((yaw).abs() < 0.01);
        assert!((pitch).abs() < 0.01);
    }

    #[test]
    fn rotation_to_yaw_pitch_detects_yaw() {
        // 绕 Y 轴旋转 30 度（模拟左转）
        let angle = 30.0_f64.to_radians();
        let rotation = [
            [angle.cos(), 0.0, angle.sin()],
            [0.0, 1.0, 0.0],
            [-angle.sin(), 0.0, angle.cos()],
        ];
        let (yaw, pitch) = rotation_to_yaw_pitch(&rotation);
        assert!((yaw - 30.0).abs() < 0.1, "yaw={yaw}");
        assert!((pitch).abs() < 0.1, "pitch={pitch}");
    }

    #[test]
    fn model_points_are_valid() {
        assert_eq!(FACE_MODEL_POINTS_3D.len(), 6);
        // 鼻尖在原点
        assert_eq!(FACE_MODEL_POINTS_3D[0], [0.0, 0.0, 0.0]);
    }
}
