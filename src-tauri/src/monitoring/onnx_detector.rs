//! ONNX 检测器：YuNet 人脸检测 + 5 关键点 solvePnP。
//!
//! 工作流程：
//! 1. YuNet 检测人脸，输出边界框 + 5 个关键点
//! 2. 5 个 2D 关键点 + 第 6 点（下巴，由 bbox 估算）→ DLT solvePnP → 旋转矩阵
//! 3. 从旋转矩阵提取 yaw 和 pitch
//!
//! 下巴点由边界框底部中心估算，大角度（>45°）时精度会下降。

use crate::domain::classifier::HeadPose;
use crate::monitoring::detector::Detector;
use nalgebra::{self, SVD};

// ── 常量 ───────────────────────────────────────────────────────

/// YuNet 输入尺寸
const INPUT_W: u32 = 320;
const INPUT_H: u32 = 240;

/// YuNet 每个检测的输出宽度：[x, y, w, h, conf, 5×(lx, ly)]
const YUNET_DETECTION_STRIDE: usize = 15;

/// 关键点数量（YuNet 输出）
const NUM_KEYPOINTS: usize = 5;

/// solvePnP 使用的 3D 模型点总数（含下巴）
const NUM_MODEL_POINTS: usize = 6;

/// 最低置信度阈值
const MIN_CONFIDENCE: f32 = 0.5;

/// Jacobi SVD 最大迭代次数
const JACOBI_MAX_ITER: usize = 100;

/// 数值零阈值
const EPSILON: f64 = 1e-10;
const EPSILON_OFF_DIAG: f64 = 1e-15;

// ── 3D 模型点（鼻尖为原点） ───────────────────────────────────
// 前 5 个对应 YuNet 的 5 关键点：左眼、右眼、鼻尖、左嘴角、右嘴角
// 第 6 个是下巴，由边界框底部估算
const MODEL_3D: [[f64; 3]; NUM_MODEL_POINTS] = [
    [-34.0, 32.0, -30.0],  // 左眼中心
    [34.0, 32.0, -30.0],   // 右眼中心
    [0.0, 0.0, 0.0],       // 鼻尖（原点）
    [-29.0, -29.0, -25.0], // 左嘴角
    [29.0, -29.0, -25.0],  // 右嘴角
    [0.0, -75.0, -12.0],   // 下巴
];

// ── YuNet 检测器 ──────────────────────────────────────────────

/// YuNet 检测器。
///
/// 单模型方案：YuNet 输出 5 关键点，下巴从边界框底部估算，
/// 用 6 个对应点做 solvePnP 计算头部姿态。
pub struct YuNetDetector {
    session: ort::session::Session,
}

/// YuNet 单次检测结果。
struct Detection {
    landmarks_2d: [[f64; 2]; NUM_KEYPOINTS],
    bbox: [f32; 4], // x, y, w, h（输入图像坐标）
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
        let input_data = preprocess_rgb(rgb, width, height);
        let tensor = ort::value::Tensor::from_array((
            [1usize, 3, INPUT_H as usize, INPUT_W as usize],
            input_data,
        ))
        .ok()?;

        let input_name = self.session.inputs()[0].name().to_string();
        let outputs = self
            .session
            .run(ort::inputs![input_name.as_str() => tensor])
            .ok()?;

        let output = outputs[0].try_extract_array::<f32>().ok()?;
        let det = find_best_detection(output.as_slice()?, output.shape(), width, height)?;

        let points_2d = build_6_point_correspondence(&det, width, height);
        let camera_matrix = estimate_camera_matrix(width, height);
        let rotation = solve_pnp(&points_2d, &MODEL_3D, &camera_matrix)?;
        let (yaw, pitch) = rotation_to_yaw_pitch(&rotation);
        Some(HeadPose { yaw, pitch })
    }
}

/// 从 YuNet 输出中找置信度最高的人脸检测。
fn find_best_detection(
    data: &[f32],
    shape: &[usize],
    width: u32,
    height: u32,
) -> Option<Detection> {
    if shape.len() < 3 || shape[2] < YUNET_DETECTION_STRIDE {
        return None;
    }
    let num_detections = shape[1];
    let scale_x = width as f64 / INPUT_W as f64;
    let scale_y = height as f64 / INPUT_H as f64;

    let mut best_conf = MIN_CONFIDENCE;
    let mut best = None;

    for i in 0..num_detections {
        let base = i * YUNET_DETECTION_STRIDE;
        let conf = data[base + 4];
        if conf > best_conf {
            best_conf = conf;
            let mut landmarks_2d = [[0.0_f64; 2]; NUM_KEYPOINTS];
            for j in 0..NUM_KEYPOINTS {
                landmarks_2d[j] = [
                    data[base + 5 + j * 2] as f64 * scale_x,
                    data[base + 5 + j * 2 + 1] as f64 * scale_y,
                ];
            }
            best = Some(Detection {
                landmarks_2d,
                bbox: [data[base], data[base + 1], data[base + 2], data[base + 3]],
            });
        }
    }
    best
}

/// 将 5 关键点 + 下巴估算组合为 6 点对应关系。
///
/// 下巴 = 边界框底部中心。大角度时此估算有误差。
fn build_6_point_correspondence(det: &Detection, width: u32, height: u32) -> [[f64; 2]; 6] {
    let scale_x = width as f64 / INPUT_W as f64;
    let scale_y = height as f64 / INPUT_H as f64;
    let chin_x = (det.bbox[0] as f64 + det.bbox[2] as f64 / 2.0) * scale_x;
    let chin_y = (det.bbox[1] as f64 + det.bbox[3] as f64) * scale_y;
    let mut pts = [[0.0_f64; 2]; 6];
    pts[..NUM_KEYPOINTS].copy_from_slice(&det.landmarks_2d);
    pts[NUM_MODEL_POINTS - 1] = [chin_x, chin_y];
    pts
}

// ── 预处理 ─────────────────────────────────────────────────────

/// 最近邻缩放 + 转 NCHW float32。
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
            let dst_base = oy * out_w + ox;
            buf[dst_base] = rgb[src_idx] as f32;
            buf[out_h * out_w + dst_base] = rgb[src_idx + 1] as f32;
            buf[2 * out_h * out_w + dst_base] = rgb[src_idx + 2] as f32;
        }
    }
    buf
}

// ── 相机内参估计 ───────────────────────────────────────────────

/// 从图像尺寸估算相机内参矩阵。假设主点在中心，焦距 = max(w, h)。
fn estimate_camera_matrix(width: u32, height: u32) -> [[f64; 3]; 3] {
    let f = width.max(height) as f64;
    [[f, 0.0, width as f64 / 2.0], [0.0, f, height as f64 / 2.0], [0.0, 0.0, 1.0]]
}

// ── solvePnP（DLT + nalgebra SVD） ─────────────────────────────
// nalgebra 仅用于 12×12 SVD 求 DLT 零空间。项目已有 opencv crate，
// 但 opencv 的 solve_pnp 需要额外的相机标定参数且行为不同，
// 纯 Rust 实现更可控，与 onnx-detector feature 的条件编译更契合。

/// Direct Linear Transform solvePnP。
fn solve_pnp(
    points_2d: &[[f64; 2]; 6],
    points_3d: &[[f64; 3]; 6],
    camera_matrix: &[[f64; 3]; 3],
) -> Option<[[f64; 3]; 3]> {
    let a_data = build_dlt_matrix(points_2d, points_3d, camera_matrix);
    let p_vec = dlt_null_space(&a_data)?;
    let r_raw = extract_rotation_raw(&p_vec);
    orthogonalize_rotation(&r_raw)
}

/// 构建 DLT A 矩阵（12×12），行优先存储。
fn build_dlt_matrix(
    points_2d: &[[f64; 2]; 6],
    points_3d: &[[f64; 3]; 6],
    camera_matrix: &[[f64; 3]; 3],
) -> [f64; 144] {
    let fx = camera_matrix[0][0];
    let fy = camera_matrix[1][1];
    let cx = camera_matrix[0][2];
    let cy = camera_matrix[1][2];
    let mut a = [0.0f64; 144];
    for i in 0..6 {
        let [x, y, z] = points_3d[i];
        let u = (points_2d[i][0] - cx) / fx;
        let v = (points_2d[i][1] - cy) / fy;
        let r0 = 2 * i;
        let r1 = r0 + 1;
        a[r0 * 12..r0 * 12 + 12]
            .copy_from_slice(&[x, y, z, 1.0, 0.0, 0.0, 0.0, 0.0, -u * x, -u * y, -u * z, -u]);
        a[r1 * 12..r1 * 12 + 12]
            .copy_from_slice(&[0.0, 0.0, 0.0, 0.0, x, y, z, 1.0, -v * x, -v * y, -v * z, -v]);
    }
    a
}

/// 用 nalgebra SVD 求 DLT 矩阵的零空间向量。
fn dlt_null_space(a_data: &[f64; 144]) -> Option<Vec<f64>> {
    let a_mat = nalgebra::DMatrix::from_row_slice(12, 12, a_data);
    let svd = SVD::new(a_mat, true, true);
    let v_t = svd.v_t.as_ref()?;
    Some(v_t.row(11).iter().copied().collect())
}

/// 从 DLT 解向量提取原始旋转矩阵。
fn extract_rotation_raw(p_vec: &[f64]) -> [[f64; 3]; 3] {
    let mut r = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            r[i][j] = p_vec[i * 4 + j];
        }
    }
    r
}

/// SVD 正交化为 SO(3)，确保 det(R) = +1。
fn orthogonalize_rotation(r_raw: &[[f64; 3]; 3]) -> Option<[[f64; 3]; 3]> {
    let (u, _s, vt) = svd3x3(r_raw)?;
    let mut r = mat_mul_3x3(&u, &vt);
    if det3x3(&r) < 0.0 {
        for row in &mut r {
            for x in row.iter_mut() {
                *x = -*x;
            }
        }
    }
    Some(r)
}

// ── 线性代数工具 ───────────────────────────────────────────────

/// 3×3 矩阵乘法。
fn mat_mul_3x3(a: &[[f64; 3]; 3], b: &[[f64; 3]; 3]) -> [[f64; 3]; 3] {
    let mut out = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            out[i][j] = (0..3).map(|k| a[i][k] * b[k][j]).sum();
        }
    }
    out
}

/// 3×3 行列式。
fn det3x3(m: &[[f64; 3]; 3]) -> f64 {
    m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
}

/// 3×3 Jacobi SVD。
///
/// 返回 (U, sigma, V^T)，使得 A = U * diag(sigma) * V^T。
fn svd3x3(a: &[[f64; 3]; 3]) -> Option<([[f64; 3]; 3], [f64; 3], [[f64; 3]; 3])> {
    let ata = mat_transpose_times_self(a);
    let (mut v, s) = jacobi_eigen_3x3(&ata);
    let mut sigma = eigenvalues_to_sigma(&s);
    sort_descending(&mut sigma, &mut v);
    let u = compute_u(a, &v, &sigma);
    let u = orthogonalize_u(u, &sigma);
    let vt = transpose_3x3(&v);
    Some((u, sigma, vt))
}

/// 计算 A^T A。
fn mat_transpose_times_self(a: &[[f64; 3]; 3]) -> [[f64; 3]; 3] {
    let mut ata = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            ata[i][j] = (0..3).map(|k| a[k][i] * a[k][j]).sum();
        }
    }
    ata
}

/// Jacobi 迭代求 3×3 对称矩阵的特征值和特征向量。
fn jacobi_eigen_3x3(matrix: &[[f64; 3]; 3]) -> ([[f64; 3]; 3], [[f64; 3]; 3]) {
    let mut v = [[0.0f64; 3]; 3];
    v[0][0] = 1.0;
    v[1][1] = 1.0;
    v[2][2] = 1.0;
    let mut s = *matrix;

    for _ in 0..JACOBI_MAX_ITER {
        let mut converged = true;
        for p in 0..3 {
            for q in (p + 1)..3 {
                if s[p][q].abs() < EPSILON_OFF_DIAG {
                    continue;
                }
                converged = false;
                jacobi_rotate(&mut s, &mut v, p, q);
            }
        }
        if converged {
            break;
        }
    }
    (v, s)
}

/// 对 (p, q) 位置执行一次 Jacobi 旋转。
fn jacobi_rotate(s: &mut [[f64; 3]; 3], v: &mut [[f64; 3]; 3], p: usize, q: usize) {
    let tau = (s[q][q] - s[p][p]) / (2.0 * s[p][q]);
    let t = if tau >= 0.0 {
        1.0 / (tau + (1.0 + tau * tau).sqrt())
    } else {
        -1.0 / (-tau + (1.0 + tau * tau).sqrt())
    };
    let c = 1.0 / (1.0 + t * t).sqrt();
    let st = t * c;

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
    for r in 0..3 {
        let vrp = v[r][p];
        let vrq = v[r][q];
        v[r][p] = c * vrp - st * vrq;
        v[r][q] = st * vrp + c * vrq;
    }
}

/// 从对称矩阵的特征值计算奇异值（sqrt of max(eigenvalue, 0)）。
fn eigenvalues_to_sigma(s: &[[f64; 3]; 3]) -> [f64; 3] {
    [s[0][0].max(0.0).sqrt(), s[1][1].max(0.0).sqrt(), s[2][2].max(0.0).sqrt()]
}

/// 按奇异值降序排列 sigma 和对应的 V 列。
fn sort_descending(sigma: &mut [f64; 3], v: &mut [[f64; 3]; 3]) {
    let mut indices = [0, 1, 2];
    indices.sort_by(|&i, &j| {
        sigma[j].partial_cmp(&sigma[i]).unwrap_or(std::cmp::Ordering::Equal)
    });
    let orig_sigma = *sigma;
    let orig_v = *v;
    for (new_i, &old_i) in indices.iter().enumerate() {
        sigma[new_i] = orig_sigma[old_i];
        for r in 0..3 {
            v[r][new_i] = orig_v[r][old_i];
        }
    }
}

/// U = A * V * Sigma^{-1}。
fn compute_u(a: &[[f64; 3]; 3], v: &[[f64; 3]; 3], sigma: &[f64; 3]) -> [[f64; 3]; 3] {
    let mut u = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            if sigma[j] > EPSILON {
                u[i][j] = (0..3).map(|k| a[i][k] * v[k][j]).sum::<f64>() / sigma[j];
            } else {
                u[i][j] = if i == j { 1.0 } else { 0.0 };
            }
        }
    }
    u
}

/// Gram-Schmidt 正交化 U 中对应零奇异值的列。
fn orthogonalize_u(mut u: [[f64; 3]; 3], sigma: &[f64; 3]) -> [[f64; 3]; 3] {
    for col in 0..3 {
        if sigma[col] < EPSILON {
            for prev in 0..col {
                let dot: f64 = (0..3).map(|i| u[i][col] * u[i][prev]).sum();
                for i in 0..3 {
                    u[i][col] -= dot * u[i][prev];
                }
            }
            let norm: f64 = (0..3).map(|i| u[i][col] * u[i][col]).sum::<f64>().sqrt();
            if norm > EPSILON {
                for i in 0..3 {
                    u[i][col] /= norm;
                }
            }
        }
    }
    u
}

/// 3×3 矩阵转置。
fn transpose_3x3(m: &[[f64; 3]; 3]) -> [[f64; 3]; 3] {
    let mut t = [[0.0f64; 3]; 3];
    for i in 0..3 {
        for j in 0..3 {
            t[i][j] = m[j][i];
        }
    }
    t
}

/// 从旋转矩阵提取 yaw 和 pitch（度数）。
///
/// 与 Python 版 `head_pose_geometry.rotation_to_yaw_pitch` 行为一致：
/// - yaw = atan2(R[0][2], R[2][2])（绕 Y 轴）
/// - pitch = atan2(-R[2][1], R[2][2])（绕 X 轴，取反使 positive = 仰头）
///
/// 符号约定：positive pitch = 仰头，negative pitch = 低头。
/// 取反原因：camera Y 轴向下，头部上仰时 R[2][1] = -sin(θ)，
/// atan2 直接得 -θ，取反后 positive = 仰头，与约定一致。
pub fn rotation_to_yaw_pitch(rotation: &[[f64; 3]; 3]) -> (f64, f64) {
    let yaw = rotation[0][2].atan2(rotation[2][2]);
    let pitch = -rotation[2][1].atan2(rotation[2][2]);
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

    fn project_points(r: &[[f64; 3]; 3], tz: f64, f: f64, cx: f64, cy: f64) -> [[f64; 2]; 6] {
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
        let cam = [[1000.0, 0.0, 160.0], [0.0, 1000.0, 120.0], [0.0, 0.0, 1.0]];
        let pts = project_points(&identity_matrix(), 500.0, 1000.0, 160.0, 120.0);
        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!(yaw.abs() < 5.0, "yaw={yaw}");
        assert!(pitch.abs() < 5.0, "pitch={pitch}");
    }

    #[test]
    fn solve_pnp_detects_left_turn() {
        let cam = [[1000.0, 0.0, 160.0], [0.0, 1000.0, 120.0], [0.0, 0.0, 1.0]];
        let r_true = yaw_rotation_matrix(-25.0);
        let pts = project_points(&r_true, 500.0, 1000.0, 160.0, 120.0);
        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!((yaw - (-25.0)).abs() < 5.0, "yaw={yaw}");
        assert!(pitch.abs() < 5.0, "pitch={pitch}");
    }

    #[test]
    fn solve_pnp_detects_right_turn() {
        let cam = [[1000.0, 0.0, 160.0], [0.0, 1000.0, 120.0], [0.0, 0.0, 1.0]];
        let r_true = yaw_rotation_matrix(35.0);
        let pts = project_points(&r_true, 500.0, 1000.0, 160.0, 120.0);
        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!((yaw - 35.0).abs() < 5.0, "yaw={yaw}");
        assert!(pitch.abs() < 5.0, "pitch={pitch}");
    }

    #[test]
    fn solve_pnp_detects_pitch_up() {
        let cam = [[1000.0, 0.0, 160.0], [0.0, 1000.0, 120.0], [0.0, 0.0, 1.0]];
        // 负向绕 X 轴旋转 = 仰头
        let r_true = pitch_rotation_matrix(-20.0);
        let pts = project_points(&r_true, 500.0, 1000.0, 160.0, 120.0);
        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!(yaw.abs() < 5.0, "yaw={yaw}");
        assert!(pitch > 5.0, "仰头应为正 pitch, got {pitch}");
    }

    #[test]
    fn solve_pnp_detects_pitch_down() {
        let cam = [[1000.0, 0.0, 160.0], [0.0, 1000.0, 120.0], [0.0, 0.0, 1.0]];
        // 正向绕 X 轴旋转 = 低头
        let r_true = pitch_rotation_matrix(15.0);
        let pts = project_points(&r_true, 500.0, 1000.0, 160.0, 120.0);
        let r = solve_pnp(&pts, &MODEL_3D, &cam).unwrap();
        let (yaw, pitch) = rotation_to_yaw_pitch(&r);
        assert!(yaw.abs() < 5.0, "yaw={yaw}");
        assert!(pitch < -5.0, "低头应为负 pitch, got {pitch}");
    }

    // ── svd3x3 ─────────────────────────────────────────────────

    #[test]
    fn svd3x3_identity() {
        let (u, s, vt) = svd3x3(&identity_matrix()).unwrap();
        for i in 0..3 {
            assert!((s[i] - 1.0).abs() < 0.01, "sigma[{i}]={}", s[i]);
        }
        let recon = mat_mul_3x3(&mat_mul_3x3(&u, &diag_matrix(&s)), &vt);
        for i in 0..3 {
            for j in 0..3 {
                let expected = if i == j { 1.0 } else { 0.0 };
                assert!((recon[i][j] - expected).abs() < 0.01, "recon[{i}][{j}]={}", recon[i][j]);
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

    // ── 其他 ───────────────────────────────────────────────────

    #[test]
    fn camera_matrix_centered() {
        let cam = estimate_camera_matrix(640, 480);
        assert!((cam[0][0] - 640.0).abs() < 0.01);
        assert!((cam[0][2] - 320.0).abs() < 0.01);
        assert!((cam[1][2] - 240.0).abs() < 0.01);
    }

    #[test]
    fn preprocess_output_size() {
        let rgb = vec![0u8; 640 * 480 * 3];
        let out = preprocess_rgb(&rgb, 640, 480);
        assert_eq!(out.len(), 3 * 240 * 320);
    }

    #[test]
    fn model_3d_nose_at_origin() {
        assert_eq!(MODEL_3D[2], [0.0, 0.0, 0.0]);
    }

    // ── 测试辅助 ───────────────────────────────────────────────

    fn identity_matrix() -> [[f64; 3]; 3] {
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    }

    fn yaw_rotation_matrix(deg: f64) -> [[f64; 3]; 3] {
        let r = deg.to_radians();
        [[r.cos(), 0.0, r.sin()], [0.0, 1.0, 0.0], [-r.sin(), 0.0, r.cos()]]
    }

    fn pitch_rotation_matrix(deg: f64) -> [[f64; 3]; 3] {
        let r = deg.to_radians();
        [[1.0, 0.0, 0.0], [0.0, r.cos(), -r.sin()], [0.0, r.sin(), r.cos()]]
    }

    fn diag_matrix(d: &[f64; 3]) -> [[f64; 3]; 3] {
        [[d[0], 0.0, 0.0], [0.0, d[1], 0.0], [0.0, 0.0, d[2]]]
    }

    #[test]
    fn latency_benchmark() {
        use crate::monitoring::detector::Detector;
        use std::time::Instant;

        let model_path = "../models/face_detection_yunet_2023mar.onnx";
        if !std::path::Path::new(model_path).exists() {
            eprintln!("latency_benchmark: 模型文件不存在，跳过 ({model_path})");
            return;
        }
        let mut detector = YuNetDetector::new(model_path).expect("加载模型失败");
        let frame = vec![0u8; 640 * 480 * 3];
        let n = 30usize;
        let mut durations: Vec<f64> = (0..n)
            .map(|_| {
                let t = Instant::now();
                let _ = detector.detect(&frame, 640, 480);
                t.elapsed().as_secs_f64() * 1000.0
            })
            .collect();
        durations.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let p50 = durations[n * 50 / 100];
        let p95 = durations[(n * 95 / 100).min(n - 1)];
        let p99 = durations[(n * 99 / 100).min(n - 1)];
        eprintln!("YuNet 延迟 (N={n}):");
        eprintln!("  P50: {p50:.1} ms");
        eprintln!("  P95: {p95:.1} ms");
        eprintln!("  P99: {p99:.1} ms");
    }
}
