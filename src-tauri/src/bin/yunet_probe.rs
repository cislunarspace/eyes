/// YuNet 探针：验证模型加载正常，打印基本信息。
///
/// 用法：cargo run --features onnx-detector --bin yunet_probe -- [model_path]
///
/// 若不传路径，默认读取 models/face_detection_yunet_2023mar.onnx。
/// 此工具不打开摄像头——运行通过后，自行将真实帧传给 detect()。
use eyes_lib::monitoring::detector::Detector;
use eyes_lib::monitoring::onnx_detector::YuNetDetector;

fn main() {
    let model_path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "models/face_detection_yunet_2023mar.onnx".to_string());

    let mut detector = match YuNetDetector::new(&model_path) {
        Ok(d) => {
            println!("✅ 模型加载成功: {model_path}");
            d
        }
        Err(e) => {
            eprintln!("❌ 加载失败: {e}");
            std::process::exit(1);
        }
    };

    // 用全黑帧探测（预期无人脸）
    let black = vec![0u8; 640 * 480 * 3];
    let result = detector.detect(&black, 640, 480);
    println!("✅ detect(黑帧 640×480) = {result:?}  (黑帧预期 None)");

    // 延迟基准：30 帧
    let mut durations = Vec::with_capacity(30);
    for _ in 0..30 {
        let t = std::time::Instant::now();
        let _ = detector.detect(&black, 640, 480);
        durations.push(t.elapsed().as_micros());
    }
    durations.sort_unstable();
    let p50 = durations[14] as f64 / 1000.0;
    let p95 = durations[28] as f64 / 1000.0;
    let p99 = durations[29] as f64 / 1000.0;
    println!("📊 延迟（黑帧，30 次）: P50={p50:.2} ms  P95={p95:.2} ms  P99={p99:.2} ms");
    println!("✅ Probe 完成。下一步：替换 detect() 的输入帧为真实摄像头帧，验证 5 种姿态。");
}
