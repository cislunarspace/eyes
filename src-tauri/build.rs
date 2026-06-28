use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());

    // 复制 OpenCV DLL 到 src-tauri/ 供 Tauri 打包
    if let Ok(link_paths) = std::env::var("OPENCV_LINK_PATHS") {
        for dir in link_paths.split(';').filter(|s| !s.is_empty()) {
            if let Ok(entries) = fs::read_dir(dir) {
                for entry in entries.flatten() {
                    let name = entry.file_name().to_string_lossy().to_lowercase();
                    if name.starts_with("opencv_world") && name.ends_with(".dll") {
                        let dest = manifest_dir.join(entry.file_name());
                        if fs::copy(entry.path(), &dest).is_ok() {
                            println!("cargo:warning=复制 {} 到 src-tauri/", name);
                        }
                    }
                }
            }
        }
    }

    // 复制 ONNX Runtime DLL 到 src-tauri/ 供 Tauri 打包
    if let Ok(ort_dir) = std::env::var("ORT_LIB_LOCATION") {
        let ort_dll = PathBuf::from(&ort_dir).join("onnxruntime.dll");
        if ort_dll.exists() {
            let dest = manifest_dir.join("onnxruntime.dll");
            if fs::copy(&ort_dll, &dest).is_ok() {
                println!("cargo:warning=复制 onnxruntime.dll 到 src-tauri/");
            }
        }
    }

    // 如果 onnxruntime.dll 不存在，创建空占位文件防止 tauri_build 报错
    let ort_placeholder = manifest_dir.join("onnxruntime.dll");
    if !ort_placeholder.exists() {
        fs::write(&ort_placeholder, []).expect("无法创建 onnxruntime.dll 占位文件");
    }

    tauri_build::build();
}
