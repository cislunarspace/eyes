/// 摄像头实测工具：实时打印 YuNet yaw/pitch，用于 5 姿态验证。
///
/// 用法：cargo run --features onnx-detector,opencv-camera --bin yunet_camera -- [model_path]
///
/// 按键：
///   s — 截图保存到当前目录（调试用）
///   q / Esc — 退出
///
/// 验收：分别做出 5 种姿态，观察输出是否符合预期。
#[cfg(not(feature = "opencv-camera"))]
fn main() {
    eprintln!("❌ 需要 opencv-camera feature。");
    eprintln!("   cargo run --features onnx-detector,opencv-camera --bin yunet_camera");
    std::process::exit(1);
}

#[cfg(feature = "opencv-camera")]
fn main() -> Result<(), Box<dyn std::error::Error>> {
    use eyes_lib::monitoring::detector::Detector;
    use eyes_lib::monitoring::onnx_detector::YuNetDetector;
    use opencv::{core, highgui, prelude::*, videoio};

    let model_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "models/face_detection_yunet_2023mar.onnx".to_string());

    let mut detector = YuNetDetector::new(&model_path).map_err(|e| {
        eprintln!("❌ 模型加载失败: {e}");
        e
    })?;
    println!("✅ 模型加载成功: {model_path}");

    let mut cap = videoio::VideoCapture::new(0, videoio::CAP_ANY)?;
    if !cap.is_opened()? {
        eprintln!("❌ 无法打开摄像头");
        std::process::exit(1);
    }
    println!("✅ 摄像头已打开");
    println!("按键: s=截图  q/Esc=退出\n");

    let window = "YuNet Pose Test";
    highgui::named_window(window, highgui::WINDOW_AUTOSIZE)?;

    let mut frame = core::Mat::default();
    let mut bgr_buf = core::Vector::<u8>::new();

    loop {
        cap.read(&mut frame)?;
        if frame.empty() {
            continue;
        }

        let rows = frame.rows();
        let cols = frame.cols();

        // BGR → RGB bytes
        let mut rgb = vec![0u8; (rows * cols * 3) as usize];
        for y in 0..rows {
            for x in 0..cols {
                let bgr = frame.at_2d::<core::Vec3b>(y, x)?;
                let idx = ((y * cols + x) * 3) as usize;
                rgb[idx] = bgr[2];     // R
                rgb[idx + 1] = bgr[1]; // G
                rgb[idx + 2] = bgr[0]; // B
            }
        }

        // 检测
        let result = detector.detect(&rgb, cols as u32, rows as u32);
        let label = match result {
            Some(pose) => {
                format!("yaw={:+.1}° pitch={:+.1}°", pose.yaw, pose.pitch)
            }
            None => "No face".to_string(),
        };

        // 在帧上绘制文字
        opencv::imgproc::put_text(
            &mut frame,
            &label,
            core::Point::new(10, 30),
            opencv::imgproc::FONT_HERSHEY_SIMPLEX,
            0.8,
            core::Scalar::new(0.0, 255.0, 0.0, 0.0),
            2,
            opencv::imgproc::LINE_AA,
            false,
        )?;

        highgui::imshow(window, &frame)?;

        let key = highgui::wait_key(1)?;
        match (key & 0xFF) as u8 {
            // q 或 Esc
            b'q' | 27 => break,
            // s — 截图
            b's' => {
                let name = format!("pose_{}.png", chrono_label());
                opencv::imgcodecs::imwrite(&name, &frame, &core::Vector::new())?;
                println!("💾 截图保存: {name}");
            }
            _ => {}
        }
    }

    highgui::destroy_all_windows()?;
    Ok(())
}

fn chrono_label() -> String {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        .to_string()
}
