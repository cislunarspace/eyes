"""摄像头实测工具：用现有 Python MediaPipe 检测器验证 5 种姿态。

用法：cd eyes && py tests/manual_pose_check.py

按键：
  空格 — 打印当前 yaw/pitch
  q    — 退出

需验收的 5 种姿态：
  正面        yaw ≈ 0°  pitch ≈ 0°
  左转 ~30°   yaw < -10° pitch ≈ 0°
  右转 ~30°   yaw > +10° pitch ≈ 0°
  仰头        yaw ≈ 0°  pitch > +5°
  低头        yaw ≈ 0°  pitch < -5°
"""
import cv2
from eyes.detector import HeadPoseDetector

def main():
    print("✅ 加载 MediaPipe 检测器...")
    detector = HeadPoseDetector()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开摄像头")
        return

    print("✅ 摄像头已打开")
    print("按键: 空格=打印  q=退出\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        pose = detector.detect(frame)

        # 绘制信息
        if pose is not None:
            label = f"yaw={pose.yaw:+.1f} pitch={pose.pitch:+.1f}"
        else:
            label = "No face"

        cv2.putText(frame, label, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("Pose Test", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord(' '):
            print(f"  {label}")

    cap.release()
    cv2.destroyAllWindows()
    detector.close()

if __name__ == "__main__":
    main()
