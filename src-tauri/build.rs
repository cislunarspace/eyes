use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());

    // 复制 OpenCV DLL 到 src-tauri/ 供 Tauri 打包
    if let Ok(link_paths) = std::env::var("OPENCV_LINK_PATHS") {
        for dir in std::env::split_paths(&link_paths) {
            if let Ok(entries) = fs::read_dir(&dir) {
                for entry in entries.flatten() {
                    let name = entry.file_name().to_string_lossy().to_lowercase();
                    if name.starts_with("opencv_world") && name.ends_with(".dll") {
                        let dest = manifest_dir.join(entry.file_name());
                        match fs::copy(entry.path(), &dest) {
                            Ok(_) => println!("cargo:warning=复制 {} 到 src-tauri/", name),
                            Err(e) => println!("cargo:warning=复制 {} 失败: {}", name, e),
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
            match fs::copy(&ort_dll, &dest) {
                Ok(_) => println!("cargo:warning=复制 onnxruntime.dll 到 src-tauri/"),
                Err(e) => println!("cargo:warning=复制 onnxruntime.dll 失败: {}", e),
            }
        }
    }

    // DLL 不存在时创建空占位文件，防止 tauri_build 报错。
    // 正式打包时 build-windows.cmd 会确保 DLL 已就位。
    ensure_dll_placeholder(&manifest_dir, "onnxruntime.dll");
    ensure_dll_placeholder(&manifest_dir, "opencv_world4100.dll");

    tauri_build::build();
}

/// DLL 不存在时创建 0 字节占位文件。
///
/// 占位文件仅用于通过 tauri_build 的资源验证。
/// 正式 MSI 打包前必须用真实 DLL 替换（由 build-windows.cmd 保证）。
fn ensure_dll_placeholder(manifest_dir: &PathBuf, name: &str) {
    let path = manifest_dir.join(name);
    if !path.exists() {
        fs::write(&path, []).unwrap_or_else(|e| {
            panic!("无法创建 {} 占位文件: {}", name, e);
        });
    }
}
