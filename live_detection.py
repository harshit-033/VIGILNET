"""
College Inspector AI - Real-time Phone Camera Stream Detection
Streams video from phone camera (IP Webcam / RTSP / HTTP) and performs real-time detection & segmentation using the trained models.

Usage:
    python live_detection.py
    python live_detection.py --url http://152.20.19.147:8080/video --model defect
    python live_detection.py --url http://152.20.19.147:8080/video --model monitor
    python live_detection.py --url http://152.20.19.147:8080/video --model both
"""

import os
import sys
import time
import argparse
from pathlib import Path
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    print("[ERROR] 'ultralytics' library is not installed.")
    print("Please install dependencies using: pip install ultralytics opencv-python torch torchvision")
    sys.exit(1)

# Default paths and configurations
DEFAULT_STREAM_URL = "http://100.97.0.199:8080/video"
BASE_DIR = Path(__file__).resolve().parent

DEFECT_MODEL_PATH = BASE_DIR / "models" / "college_inspector_yolo11s_seg_best.pt"
MONITOR_MODEL_PATH = BASE_DIR / "models" / "monitor_detection" / "computer_monitor_detection_yolov8s_best.pt"

# Colors for bounding boxes / HUD (BGR)
CLASS_COLORS = {
    "crack": (0, 0, 255),          # Red
    "spalling": (0, 140, 255),      # Orange
    "corrosion": (0, 255, 255),     # Yellow
    "efflorescence": (255, 0, 255), # Magenta
    "monitor": (0, 255, 0),         # Green
    "default": (255, 200, 0)        # Cyan
}


def draw_hud(frame, fps, active_mode_name, detections_summary, conf_threshold):
    """Draws an informative HUD overlay on the video stream."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    # Top banner background
    banner_height = 80
    cv2.rectangle(overlay, (0, 0), (w, banner_height), (20, 20, 20), -1)
    
    # Left status box
    cv2.putText(overlay, f"MODEL: {active_mode_name}", (15, 30),
                cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(overlay, f"FPS: {fps:.1f} | CONF: {conf_threshold:.2f} | Controls: [1] Defect [2] Monitor [3] Both [S] Save [Q] Quit",
                (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    # Blend banner
    alpha = 0.75
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    # Right side detection counts badges
    badge_x = w - 240
    badge_y = 100
    if detections_summary:
        # Background box for detections
        box_h = 30 + len(detections_summary) * 25
        sub_overlay = frame.copy()
        cv2.rectangle(sub_overlay, (badge_x - 10, badge_y - 20), (w - 10, badge_y + box_h - 20), (15, 15, 15), -1)
        cv2.addWeighted(sub_overlay, 0.7, frame, 0.3, 0, frame)

        cv2.putText(frame, "DETECTIONS:", (badge_x, badge_y),
                    cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)
        
        offset = 25
        for cls_name, count in detections_summary.items():
            color = CLASS_COLORS.get(cls_name.lower(), CLASS_COLORS["default"])
            cv2.putText(frame, f"- {cls_name}: {count}", (badge_x, badge_y + offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            offset += 25


def run_pipeline(url, initial_mode="defect", conf_threshold=0.30, imgsz=640, device=""):
    """
    Main detection pipeline connecting to the phone stream URL.
    """
    print(f"\n========================================================")
    print(f" College Inspector AI - Real-Time Live Detection System ")
    print(f"========================================================")
    print(f"Stream URL: {url}")
    print(f"Defect Model: {DEFECT_MODEL_PATH}")
    print(f"Monitor Model: {MONITOR_MODEL_PATH}")
    print(f"Initial Confidence: {conf_threshold}")
    print(f"Inference Image Size: {imgsz}x{imgsz}")
    print(f"========================================================\n")

    # Load models
    defect_model = None
    monitor_model = None

    if DEFECT_MODEL_PATH.exists():
        print(f"[INFO] Loading Structural Defect YOLO11s-Seg model...")
        defect_model = YOLO(str(DEFECT_MODEL_PATH))
    else:
        print(f"[WARNING] Defect model not found at {DEFECT_MODEL_PATH}")

    if MONITOR_MODEL_PATH.exists():
        print(f"[INFO] Loading Computer Monitor YOLOv8s model...")
        monitor_model = YOLO(str(MONITOR_MODEL_PATH))
    else:
        print(f"[WARNING] Monitor model not found at {MONITOR_MODEL_PATH}")

    if not defect_model and not monitor_model:
        print("[ERROR] No valid models found in the models directory.")
        sys.exit(1)

    # Current active mode: 'defect', 'monitor', 'both'
    mode = initial_mode
    if mode == "defect" and not defect_model:
        mode = "monitor" if monitor_model else "defect"
    elif mode == "monitor" and not monitor_model:
        mode = "defect" if defect_model else "monitor"

    print(f"[INFO] Connecting to camera stream at {url} ...")
    cap = cv2.VideoCapture(url)

    if not cap.isOpened():
        print(f"[ERROR] Could not open video stream from {url}")
        print("Please verify:")
        print(" 1. Your phone and PC are connected to the same Wi-Fi network.")
        print(" 2. IP Webcam app (or equivalent) is running on your phone and broadcasting.")
        print(" 3. The IP and Port match the URL.\n")
        print("Trying to fallback to default webcam (0)...")
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[ERROR] Unable to access fallback webcam. Exiting.")
            sys.exit(1)

    # Screenshot directory
    screenshot_dir = BASE_DIR / "detections_output"
    screenshot_dir.mkdir(exist_ok=True)

    prev_time = time.time()
    fps = 0.0

    window_name = "College Inspector AI - Live Detection"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    print("\n[READY] Video feed started.")
    print("Keyboard Shortcuts:")
    print("  '1' -> Switch to Defect Segmentation Model")
    print("  '2' -> Switch to Computer Monitor Detection Model")
    print("  '3' -> Switch to Combined (Both Models)")
    print("  '+' / '=' -> Increase confidence threshold (+0.05)")
    print("  '-' / '_' -> Decrease confidence threshold (-0.05)")
    print("  's' -> Save annotated screenshot")
    print("  'q' / ESC -> Quit\n")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Lost connection to camera stream. Attempting to reconnect...")
                time.sleep(1)
                cap.release()
                cap = cv2.VideoCapture(url)
                if not cap.isOpened():
                    continue
                ret, frame = cap.read()
                if not ret:
                    continue

            # Calculate FPS
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else fps
            prev_time = curr_time

            detections_summary = {}
            annotated_frame = frame.copy()

            # Execute Model Inference based on Mode
            if mode == "defect" and defect_model:
                mode_label = "Defect Segmentation (YOLO11s-Seg)"
                results = defect_model.predict(
                    source=frame,
                    conf=conf_threshold,
                    iou=0.30,
                    imgsz=imgsz,
                    device=device if device else None,
                    verbose=False
                )
                if results and len(results) > 0:
                    annotated_frame = results[0].plot()
                    boxes = results[0].boxes
                    if boxes is not None and boxes.cls is not None:
                        for cls_id in boxes.cls:
                            name = defect_model.names.get(int(cls_id), f"Class {int(cls_id)}")
                            detections_summary[name] = detections_summary.get(name, 0) + 1

            elif mode == "monitor" and monitor_model:
                mode_label = "Monitor Detection (YOLOv8s)"
                # Monitor model uses a lower default conf threshold as recommended in its README if conf_threshold is high
                eff_conf = min(conf_threshold, 0.25)
                results = monitor_model.predict(
                    source=frame,
                    conf=eff_conf,
                    iou=0.30,
                    imgsz=imgsz,
                    device=device if device else None,
                    verbose=False
                )
                if results and len(results) > 0:
                    annotated_frame = results[0].plot()
                    boxes = results[0].boxes
                    if boxes is not None and boxes.cls is not None:
                        for cls_id in boxes.cls:
                            name = monitor_model.names.get(int(cls_id), "Monitor")
                            detections_summary[name] = detections_summary.get(name, 0) + 1

            elif mode == "both":
                mode_label = "Combined (Defects + Monitors)"
                # Run defect segmentation
                if defect_model:
                    res_defect = defect_model.predict(
                        source=frame,
                        conf=conf_threshold,
                        iou=0.30,
                        imgsz=imgsz,
                        device=device if device else None,
                        verbose=False
                    )
                    if res_defect and len(res_defect) > 0:
                        annotated_frame = res_defect[0].plot()
                        if res_defect[0].boxes is not None and res_defect[0].boxes.cls is not None:
                            for cls_id in res_defect[0].boxes.cls:
                                name = defect_model.names.get(int(cls_id), f"Class {int(cls_id)}")
                                detections_summary[name] = detections_summary.get(name, 0) + 1

                # Run monitor detection on top
                if monitor_model:
                    eff_conf = min(conf_threshold, 0.25)
                    res_mon = monitor_model.predict(
                        source=frame,
                        conf=eff_conf,
                        iou=0.30,
                        imgsz=imgsz,
                        device=device if device else None,
                        verbose=False
                    )
                    if res_mon and len(res_mon) > 0 and res_mon[0].boxes is not None:
                        boxes = res_mon[0].boxes
                        for box, cls_id, conf in zip(boxes.xyxy, boxes.cls, boxes.conf):
                            x1, y1, x2, y2 = map(int, box)
                            name = monitor_model.names.get(int(cls_id), "Monitor")
                            detections_summary[name] = detections_summary.get(name, 0) + 1
                            # Draw monitor bounding box & label in distinct bright green
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label = f"{name} {conf:.2f}"
                            cv2.putText(annotated_frame, label, (x1, max(20, y1 - 8)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            else:
                mode_label = f"Idle ({mode})"

            # Render HUD overlay
            draw_hud(annotated_frame, fps, mode_label, detections_summary, conf_threshold)

            # Display
            cv2.imshow(window_name, annotated_frame)

            # Key controls
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' or ESC
                print("[INFO] Exiting detection stream.")
                break
            elif key == ord('1'):
                if defect_model:
                    mode = "defect"
                    print("[SWITCH] Switched to Defect Segmentation Model.")
                else:
                    print("[WARNING] Defect model is not available.")
            elif key == ord('2'):
                if monitor_model:
                    mode = "monitor"
                    print("[SWITCH] Switched to Computer Monitor Detection Model.")
                else:
                    print("[WARNING] Monitor model is not available.")
            elif key == ord('3'):
                if defect_model and monitor_model:
                    mode = "both"
                    print("[SWITCH] Switched to Combined Mode.")
                else:
                    print("[WARNING] Both models must be available for combined mode.")
            elif key == ord('+') or key == ord('='):
                conf_threshold = min(0.95, round(conf_threshold + 0.05, 2))
                print(f"[CONF] Confidence threshold increased to {conf_threshold}")
            elif key == ord('-') or key == ord('_'):
                conf_threshold = max(0.05, round(conf_threshold - 0.05, 2))
                print(f"[CONF] Confidence threshold decreased to {conf_threshold}")
            elif key == ord('s'):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                save_path = screenshot_dir / f"detection_{mode}_{timestamp}.jpg"
                cv2.imwrite(str(save_path), annotated_frame)
                print(f"[SAVED] Screenshot saved to: {save_path}")

    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description="College Inspector AI - Live Phone Camera Detection & Segmentation"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_STREAM_URL,
        help=f"IP camera stream URL (default: {DEFAULT_STREAM_URL})"
    )
    parser.add_argument(
        "--model",
        type=str,
        choices=["defect", "monitor", "both"],
        default="defect",
        help="Initial model to use: 'defect' (Defect Segmentation), 'monitor' (Computer Monitor Detection), or 'both'"
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.35,
        help="Detection confidence threshold (default: 0.35)"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Inference image resolution (default: 640 for smooth real-time video, use 1024 for higher accuracy)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="",
        help="Compute device: 'cuda', 'cpu', or '' (auto-detect GPU if available)"
    )

    args = parser.parse_args()

    run_pipeline(
        url=args.url,
        initial_mode=args.model,
        conf_threshold=args.conf,
        imgsz=args.imgsz,
        device=args.device
    )


if __name__ == "__main__":
    main()
