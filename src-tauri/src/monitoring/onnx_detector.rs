//! ONNX 检测器：YuNet 人脸检测 + 5 关键点 solvePnP。
//!
//! 工作流程：
//! 1. YuNet 检测人脸，输出边界框 + 5 个关键点
//! 2. 5 个 2D 关键点 + 6 个 3D 模型点 → DLT solvePnP → 旋转矩阵
//! 3. 从旋转矩阵提取 yaw 和 pitch
//!
//! 第 6 个 3D 点（下巴）由边界框底部估算，不需要额外的关键点模型。

use crate::domain::classifier::HeadPose;
use crate::monitoring::detector::Detector;
use nalgebra::{self, SVD};

// ── YuNet 输入尺寸 ──────────────────────────────────────────────

const INPUT_W: u32 = 320;
const INPUT_H: u32 = 240;

// ── 3D 模型点（6 点，鼻尖为原点） ──────────────────────────────
// 前 5 个对应 YuNet 的 5 关键点：左眼、右眼、鼻尖、左嘴角、右嘴角
// 第 6 个是下巴，由边界框底部估算
const MODEL_3D: [[f64; 3]; 6] = [
    [-34.0, 32.0, -30.0],  // 左眼中心
    [34.0, 32.0, -30.0],   // 右眼中心
    [0.0, 0.0, 0.0],       // 鼻尖（原点）
    [-29.0, -29.0, -25.0], // 左嘴角
    [29.0, -29.0, -25.0],  // 右嘴角
    [0.0, -75.0, -12.0],   // 下巴
];

/// YuNet 检测器。
///
/// 单模型方案：YuNet 输出 5 关键点，下巴从边界框底部估算，
/// 用 6 个对应点做 solvePnP 计算头部姿态。
pub struct YuNetDetector {
    session: ort::session::Session,
}

impl YuNetDetector {
    /// 从 ONNX 模型文件创建检测器。
    pub fn new(model_path: &str) -> Result<Self, String> {
        let session = ort::session::Session::builder()
            .map_err(|e| format!("创建 session builder 失败: {e}"))?
            .commit_from_file(model_path)
            .map_err(|e| format!("加载模型失败: {e}"))?;
        Ok(Self { session })
    }
}

impl Detector for YuNetDetector {
    fn detect(&mut self, rgb: &[u8], width: u32, height: u32) -> Option<HeadPose> {
        // Step 1: 预处理 — 最近邻缩放到 320×240，转 NCHW float32
        let input_data = preprocess_rgb(rgb, width, height);

        // Step 2: 构建输入张量
        let tensor = ort::value::Tensor::from_array((
            [1usize, 3, INPUT_H as usize, INPUT_W as usize],
            input_data,
        ))
        .ok()?;

        // Step 3: 推理
        let input_name = self.session.inputs()[0].name().to_string();
        let outputs = self
            .session
            .run(ort::inputs![input_name.as_str() => tensor])
            .ok()?;

        // Step 4: 解析输出 — YuNet 输出 [1, N, 15]
        // 每个检测：[x, y, w, h, conf, lx0, ly0, lx1, ly1, lx2, ly2, lx3, ly3, lx4, ly4]
        let output = outputs[0].try_extract_array::<f32>().ok()?;
        let shape = output.shape();
        if shape.len() < 3 || shape[2] < 15 {
            return None;
        }
        let num_detections = shape[1];
        let data = output.as_slice()?;

        // Step 5: 找置信度最高的人脸
        let mut best_conf = 0.5_f32;
        let mut best_landmarks_2d = [[0.0_f64; 2]; 5];
        let mut best_bbox = [0.0f32; 4]; // x, y, w, h

        for i in 0..num_detections {
            let base = i * 15;
            let conf = data[base + 4];
            if conf > best_conf {
                best_conf = conf;
                best_bbox = [data[base], data[base + 1], data[base + 2], data[base + 3]];
                let scale_x = width as f64 / INPUT_W as f64;
                let scale_y = height as f64 / INPUT_H as f64;
                for j in 0..5 {
                    let lx = data[base + 5 + j * 2] as f64 * scale_x;
                    let ly = data[base + 5 + j * 2 + 1] as f64 * scale_y;
                    best_landmarks_2d[j] = [lx, ly];
                }
            }
        }

        if best_conf <= 0.5 {
            return None;
        }

        // Step 6: 估算第 6 个 2D 点（下巴 = 边界框底部中心）
        let scale_x = width as f64 / INPUT_W as f64;
        let scale_y = height as f64 / INPUT_H as f64;
        let chin_x = (best_bbox[0] as f64 + best_bbox[2] as f64 / 2.0) * scale_x;
        let chin_y = (best_bbox[1] as f64 + best_bbox[3] as f64) * scale_y;
        let mut points_2d = [[0.0_f64; 2]; 6];
        points_2d[..5].copy_from_slice(&best_landmarks_2d);
        points_2d[5] = [chin_x, chin_y];

        // Step 7: solvePnP
        let camera_matrix = estimate_camera_matrix(width, height);
        let rotation = solve_pnp(&points_2d, &MODEL_3D, &camera_matrix)?;

        // Step 8: 从旋转矩阵提取 yaw 和 pitch
        let (yaw, pitch) = rotation_to_yaw_pitch(&rotation);
        Some(HeadPose { yaw, pitch })
    }
}

// ── 预处理 ─────────────────────────────────────────────────────

/// 最近邻缩放 + 转 NCHW float32。
///
/// 输入：RGB 平坦字节，width × height。
/// 输出：长度 3×240×320 的 float32 向量（CHW 顺序）。
fn preprocess_rgb(rgb: &[u8], width: u32, height: u32) -> Vec<f32> {
    debug_assert!(
        rgb.len() >= (width * height * 3) as usize,
        "rgb buffer 太小: {} < {}",
        rgb.len(),
        width * height * 3
    );
    let out_w = INPUT_W as usize;
    let out_h = INPUT_H as usize;
    let mut buf = vec![0.0f32; 3 * out_h * out_w];

    for oy in 0..out_h {
        let sy = ((oy as f64 + 0.5) * height as f64 / out_h as f64 - 0.5).round() as u32;
        let sy = sy.min(height - 1);
        for ox in 0..out_w {
            let sx = ((ox as f64 + 0.5) * width as f64 / out_w as f64 - 0.5).round() as u32;
            let sx = sx.min(width - 1);
            let src_idx = ((sy * width + sx) * 3) as usize;
            let r = rgb[src_idx] as f32;
            let g = rgb[src_idx + 1] as f32;
            let b = rgb[src_idx + 2] as f32;
            let dst_base = oy * out_w + ox;
            buf[dst_base] = r;
            buf[out_h * out_w + dst_base] = g;
            buf[2 * out_h * out_w + dst_base] = b;
        }
    }
    buf
}

// ── 相机内参估计 ───────────────────────────────────────────────

/// 从图像尺寸估算相机内参矩阵。
///
/// 假设主点在图像中心，焦距 ≈ max(width, height)。
fn estimate_camera_matrix(width: u32, height: u32) -> [[f64; 3]; 3] {
    let f = width.max(height) as f64;
    let cx = width as f64 / 2.0;
    let cy = height as f64 / 2.0;
    [[f, 0.0, cx], [0.0, f, cy], [0.0, 0.0, 1.0]]
}

// ── solvePnP（DLT + nalgebra SVD） ─────────────────────────────

/// Direct Linear Transform solvePnP。
///
/// 用 6 个 2D-3D 对应点（12 方程，12 未知数）估计旋转矩阵。
/// 使用 nalgebra SVD 求 A 的零空间向量，再 SVD 正交化为 SO(3)。
fn solve_pnp(
    points_2d: &[[f64; 2]; 6],
    points_3d: &[[f64; 3]; 6],
    camera_matrix: &[[f64; 3]; 3],
) -> Option<[[f64; 3]; 3]> {
    let fx = camera_matrix[0][0];
    let fy = camera_matrix[1][1];
    let cx = camera_matrix[0][2];
    let cy = camera_matrix[1][2];

    // 构建 A 矩阵 (12×12)
    let mut a_data = [0.0f64; 144]; // 12 rows × 12 cols
    for i in 0..6 {
        let [x3d, y3d, z3d] = points_3d[i];
        let u = (points_2d[i][0] - cx) / fx;
        let v = (points_2d[i][1] - cy) / fy;
        let row0 = 2 * i;
        let row1 = 2 * i + 1;
        // 行 row0
        a_data[row0 * 12..row0 * 12 + 12].copy_from_slice(&[
            x3d, y3d, z3d, 1.0, 0.0, 0.0, 0.0, 0.0, -u * x3d, -u * y3d, -u * z3d, -u,
        ]);
        // 行 row1
        a_data[row1 * 12..row1 * 12 + 12].copy_from_slice(&[
            0.0, 0.0, 0.0, 0.0, x3d, y3d, z3d, 1.0, -v * x3d, -v * y3d, -v * z3d, -v,
        ]);
    }

    // nalgebra SVD — 找 A 的零空间向量（最小奇异值对应的右奇异向量）
    let a_mat = nalgebra::DMatrix::from_row_slice(12, 12, &a_data);
    let svd = SVD::new(a_mat, true, true);
    let v_matrix = svd.v_t?;
    // 最小奇异值对应的右奇异向量 = V^T 的最后一行
    let last_row = v_matrix.row(11);
    let p_vec: Vec<f64> = last_row.iter().copied().collect();

    // 提取 R（前 3×3）和 t（第 4 列）
    let mut r_raw = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            r_raw[i][j] = p_vec[i * 4 + j];
        }
    }

    // SVD 正交化为 SO(3)
    let (u, _s, vt) = svd3x3(&r_raw)?;
    let mut r_proper = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            let mut s = 0.0;
            for k in 0..3 {
                s += u[i][k] * vt[k][j];
            }
            r_proper[i][j] = s;
        }
    }

    // 确保 det(R) = +1
    let det = det3x3(&r_proper);
    if det < 0.0 {
        for row in &mut r_proper {
            for x in row.iter_mut() {
                *x = -*x;
            }
        }
    }

    Some(r_proper)
}

// ── 线性代数工具 ───────────────────────────────────────────────

/// 3×3 Jacobi SVD。
///
/// 返回 (U, sigma, V^T)，使得 A = U * diag(sigma) * V^T。
fn svd3x3(a: &[[f64; 3]; 3]) -> Option<([[f64; 3]; 3], [f64; 3], [[f64; 3]; 3])> {
    // 计算 A^T A
    let mut ata = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            let mut s = 0.0;
            for k in 0..3 {
                s += a[k][i] * a[k][j];
            }
            ata[i][j] = s;
        }
    }

    // Jacobi 迭代求 A^T A 的特征值和特征向量（即 V）
    let mut v = [[0.0f64; 3]; 3];
    v[0][0] = 1.0;
    v[1][1] = 1.0;
    v[2][2] = 1.0;
    let mut s = ata;

    for _ in 0..100 {
        let mut converged = true;
        for p in 0..3 {
            for q in (p + 1)..3 {
                if s[p][q].abs() < 1e-15 {
                    continue;
                }
                converged = false;
                let tau = (s[q][q] - s[p][p]) / (2.0 * s[p][q]);
                let t = if tau >= 0.0 {
                    1.0 / (tau + (1.0 + tau * tau).sqrt())
                } else {
                    -1.0 / (-tau + (1.0 + tau * tau).sqrt())
                };
                let c = 1.0 / (1.0 + t * t).sqrt();
                let st = t * c;

                // 更新 S
                let spq = s[p][q];
                s[p][q] = 0.0;
                s[q][p] = 0.0;
                let spp = s[p][p];
                let sqq = s[q][q];
                s[p][p] = spp - t * spq;
                s[q][q] = sqq + t * spq;
                for r in 0..3 {
                    if r != p && r != q {
                        let srp = s[r][p];
                        let srq = s[r][q];
                        s[r][p] = c * srp - st * srq;
                        s[p][r] = s[r][p];
                        s[r][q] = st * srp + c * srq;
                        s[q][r] = s[r][q];
                    }
                }

                // 更新 V
                for r in 0..3 {
                    let vrp = v[r][p];
                    let vrq = v[r][q];
                    v[r][p] = c * vrp - st * vrq;
                    v[r][q] = st * vrp + c * vrq;
                }
            }
        }
        if converged {
            break;
        }
    }

    // 奇异值
    let mut sigma = [
        s[0][0].max(0.0).sqrt(),
        s[1][1].max(0.0).sqrt(),
        s[2][2].max(0.0).sqrt(),
    ];

    // 降序排列
    let mut indices = [0, 1, 2];
    indices.sort_by(|&i, &j| {
        sigma[j]
            .partial_cmp(&sigma[i])
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    let mut sorted_sigma = [0.0; 3];
    let mut sorted_v = [[0.0; 3]; 3];
    for (new_i, &old_i) in indices.iter().enumerate() {
        sorted_sigma[new_i] = sigma[old_i];
        for r in 0..3 {
            sorted_v[r][new_i] = v[r][old_i];
        }
    }
    sigma = sorted_sigma;
    v = sorted_v;

    // U = A * V * Sigma^{-1}
    let mut u = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            if sigma[j] > 1e-10 {
                let mut s_val = 0.0;
                for k in 0..3 {
                    s_val += a[i][k] * v[k][j];
                }
                u[i][j] = s_val / sigma[j];
            } else {
                u[i][j] = if i == j { 1.0 } else { 0.0 };
            }
        }
    }

    // 正交化 U（Gram-Schmidt）
    for col in 0..3 {
        if sigma[col] < 1e-10 {
            for prev in 0..col {
                let dot: f64 = (0..3).map(|i| u[i][col] * u[i][prev]).sum();
                for i in 0..3 {
                    u[i][col] -= dot * u[i][prev];
                }
            }
            let norm: f64 = (0..3).map(|i| u[i][col] * u[i][col]).sum::<f64>().sqrt();
            if norm > 1e-10 {
                for i in 0..3 {
                    u[i][col] /= norm;
                }
            }
        }
    }

    // V^T
    let mut vt = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            vt[i][j] = v[j][i];
        }
    }

    Some((u, sigma, vt))
}

/// 3×3 行列式。
fn det3x3(m: &[[f64; 3]; 3]) -> f64 {
    m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
}

/// 从旋转矩阵提取 yaw 和 pitch（度数）。
///
/// 与 Python 版 `head_pose_geometry.rotation_to_yaw_pitch` 行为一致：
/// - yaw = atan2(R[0][2], R[2][2])（绕 Y 轴）
/// - pitch = atan2(R[2][1], R[2][2])（绕 X 轴）
///
/// 符号约定：positive pitch = 仰头。
/// 坐标系：camera Y 轴向下。仰头时模型绕 X 轴正向旋转，R[2][1] = sin(θ) > 0。
pub fn rotation_to_yaw_pitch(rotation: &[[f64; 3]; 3]) -> (f64, f64) {
    let yaw = rotation[0][2].atan2(rotation[2][2]);
    let pitch = rotation[2][1].atan2(rotation[2][2]);
    (yaw.to_degrees(), pitch.to_degrees())
}

// ── 测试 ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── rotation_to_yaw_pitch ──────────────────────────────────

    #[test]
    fn identity_rotation_gives_zero() {
        let identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
        let (yaw, pitch) = rotation_to_yaw_pitch(&identity);
        assert!((yaw).abs() < 0.01);
        assert!((pitch).abs() < 0.01);
    }

    #[test]
    fn detects_yaw_rotation() {
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

    // ── solve_pnp ──────────────────────────────────────────────

    /// 用已知旋转和平移生成 6 个 2D 投影点。
    fn project_points(
        r: &[[f64; 3]; 3],
        tz: f64,
        f: f64,
        cx: f64,
        cy: f64,
    ) -> [[f64; 2]; 6] {
        std::array::from_fn(|i| {
            let [x, y, z] = MODEL_3D[i];
            let rx = r[0][0] * x + r[0][1] * y + r[0][2] * z;
            let ry = r[1][0] * x + r[1][1] * y + r[1][2] * z;
            let rz = r[2][0] * x + r[2][1] * y + r[2][2] * z;
            [f * rx / (rz + tz) + cx, f * ry / (rz + tz) + cy]
        })
    }

    #[test]
    fn solve_pnp_identity_projection() {
        let f = 1000.0;
        let cam = [[f, 0.0, 160.0], [0.0, f, 120.0], [0.0, 0.0, 1.0]];
        let identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
        let pts = project_points(&identity, 500.0, f, 160.0, 120.0);

        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!(yaw.abs() < 5.0, "yaw={yaw}");
        assert!(pitch.abs() < 5.0, "pitch={pitch}");
    }

    #[test]
    fn solve_pnp_detects_left_turn() {
        let f = 1000.0;
        let cam = [[f, 0.0, 160.0], [0.0, f, 120.0], [0.0, 0.0, 1.0]];
        // 绕 Y 轴旋转 -25 度（左转）
        let angle = -25.0_f64.to_radians();
        let r_true = [
            [angle.cos(), 0.0, angle.sin()],
            [0.0, 1.0, 0.0],
            [-angle.sin(), 0.0, angle.cos()],
        ];
        let pts = project_points(&r_true, 500.0, f, 160.0, 120.0);

        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!((yaw - (-25.0)).abs() < 5.0, "yaw={yaw}");
        assert!(pitch.abs() < 5.0, "pitch={pitch}");
    }

    #[test]
    fn solve_pnp_detects_right_turn() {
        let f = 1000.0;
        let cam = [[f, 0.0, 160.0], [0.0, f, 120.0], [0.0, 0.0, 1.0]];
        let angle = 35.0_f64.to_radians();
        let r_true = [
            [angle.cos(), 0.0, angle.sin()],
            [0.0, 1.0, 0.0],
            [-angle.sin(), 0.0, angle.cos()],
        ];
        let pts = project_points(&r_true, 500.0, f, 160.0, 120.0);

        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!((yaw - 35.0).abs() < 5.0, "yaw={yaw}");
        assert!(pitch.abs() < 5.0, "pitch={pitch}");
    }

    #[test]
    fn solve_pnp_detects_pitch_up() {
        let f = 1000.0;
        let cam = [[f, 0.0, 160.0], [0.0, f, 120.0], [0.0, 0.0, 1.0]];
        // 绕 X 轴正向旋转 20 度（仰头，camera Y 轴向下时正向 = 上仰）
        let angle = 20.0_f64.to_radians();
        let r_true = [
            [1.0, 0.0, 0.0],
            [0.0, angle.cos(), -angle.sin()],
            [0.0, angle.sin(), angle.cos()],
        ];
        let pts = project_points(&r_true, 500.0, f, 160.0, 120.0);

        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!(yaw.abs() < 5.0, "yaw={yaw}");
        // 仰头应为正 pitch
        assert!(pitch > 5.0, "仰头应为正 pitch, got {pitch}");
    }

    #[test]
    fn solve_pnp_detects_pitch_down() {
        let f = 1000.0;
        let cam = [[f, 0.0, 160.0], [0.0, f, 120.0], [0.0, 0.0, 1.0]];
        // 绕 X 轴负向旋转 15 度（低头）
        let angle = -15.0_f64.to_radians();
        let r_true = [
            [1.0, 0.0, 0.0],
            [0.0, angle.cos(), -angle.sin()],
            [0.0, angle.sin(), angle.cos()],
        ];
        let pts = project_points(&r_true, 500.0, f, 160.0, 120.0);

        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!(yaw.abs() < 5.0, "yaw={yaw}");
        // 低头应为负 pitch
        assert!(pitch < -5.0, "低头应为负 pitch, got {pitch}");
    }

    // ── svd3x3 ─────────────────────────────────────────────────

    #[test]
    fn svd3x3_identity() {
        let identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];
        let (u, s, vt) = svd3x3(&identity).unwrap();
        for i in 0..3 {
            assert!((s[i] - 1.0).abs() < 0.01, "sigma[{i}]={}", s[i]);
        }
        let mut reconstructed = [[0.0f64; 3]; 3];
        for i in 0..3 {
            for j in 0..3 {
                let mut val = 0.0;
                for k in 0..3 {
                    val += u[i][k] * s[k] * vt[k][j];
                }
                reconstructed[i][j] = val;
            }
        }
        for i in 0..3 {
            for j in 0..3 {
                let expected = if i == j { 1.0 } else { 0.0 };
                assert!(
                    (reconstructed[i][j] - expected).abs() < 0.01,
                    "recon[{i}][{j}]={}",
                    reconstructed[i][j]
                );
            }
        }
    }

    #[test]
    fn svd3x3_rank1() {
        let a = [[1.0, 2.0, 3.0], [2.0, 4.0, 6.0], [3.0, 6.0, 9.0]];
        let (_u, s, _vt) = svd3x3(&a).unwrap();
        assert!(s[0] > 1.0, "sigma[0]={}", s[0]);
        assert!(s[1].abs() < 0.1, "sigma[1]={}", s[1]);
        assert!(s[2].abs() < 0.1, "sigma[2]={}", s[2]);
    }

    // ── estimate_camera_matrix ─────────────────────────────────

    #[test]
    fn camera_matrix_centered() {
        let cam = estimate_camera_matrix(640, 480);
        assert!((cam[0][0] - 640.0).abs() < 0.01);
        assert!((cam[0][2] - 320.0).abs() < 0.01);
        assert!((cam[1][2] - 240.0).abs() < 0.01);
    }

    // ── preprocess_rgb ─────────────────────────────────────────

    #[test]
    fn preprocess_output_size() {
        let rgb = vec![0u8; 640 * 480 * 3];
        let out = preprocess_rgb(&rgb, 640, 480);
        assert_eq!(out.len(), 3 * 240 * 320);
    }

    // ── MODEL_3D ───────────────────────────────────────────────

    #[test]
    fn model_3d_nose_at_origin() {
        assert_eq!(MODEL_3D[2], [0.0, 0.0, 0.0]);
    }
}
