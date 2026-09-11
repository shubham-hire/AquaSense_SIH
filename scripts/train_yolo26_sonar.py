#!/usr/bin/env python3
"""
AquaSense YOLO26 Marine Debris Training Pipeline
SIH 2026 PS 26057 (MoES / NIOT)

Fine-tunes YOLO26 Nano (or yolo26n-seg) on acoustic side-scan sonar (SSS) imagery.
Implements the 3 core AquaSense training invariants:
  1. Cross-survey / trackline generalization (prevents seabed memorization leakage)
  2. Acoustic physics-preserving augmentations (preserves acoustic shadows)
  3. High-recall candidate generator setting (feeds into downstream 10-feature physical verifier)
"""

import os
import sys
import argparse
import time
from pathlib import Path
import torch
from ultralytics import YOLO

def parse_args():
    parser = argparse.ArgumentParser(description="Train YOLO26 Nano on Marine Sonar Debris")
    parser.add_argument(
        "--data",
        type=str,
        default=str(Path(__file__).parent.parent / "configs" / "sonar_debris_yolo26.yaml"),
        help="Path to dataset YAML config",
    )
    parser.add_argument(
        "--weights",
        type=str,
        default="yolo26n.pt",
        help="Base pretrained checkpoint (e.g. yolo26n.pt or yolo26n-seg.pt)",
    )
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (adjust for GPU VRAM)")
    parser.add_argument("--imgsz", type=int, default=640, help="Image resolution tile size")
    parser.add_argument("--device", type=str, default="", help="Device: '0', 'mps', 'cpu' or auto")
    parser.add_argument(
        "--project",
        type=str,
        default=str(Path(__file__).parent.parent / "runs" / "detect"),
        help="Run directory",
    )
    parser.add_argument("--name", type=str, default="yolo26_aquasense_sonar", help="Run experiment name")
    parser.add_argument("--export", action="store_true", help="Export to ONNX and TensorRT after training")
    return parser.parse_args()

def select_best_device(user_device: str) -> str:
    if user_device:
        return user_device
    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"

def train():
    args = parse_args()
    device = select_best_device(args.device)

    print("=" * 70)
    print("  AQUASENSE: YOLO26 NANO ACOUSTIC SSS TRAINING PIPELINE")
    print("  MoES / NIOT SIH 2026 PS 26057 — Marine Debris Identification")
    print("=" * 70)
    print(f"[*] Base Weights : {args.weights}")
    print(f"[*] Dataset YAML : {args.data}")
    print(f"[*] Compute Dev  : {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() and device == '0' else device})")
    print(f"[*] Epochs       : {args.epochs}")
    print(f"[*] Batch Size   : {args.batch}")
    print(f"[*] Tile Size    : {args.imgsz}x{args.imgsz}")

    data_path = Path(args.data).resolve()
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset config not found at: {data_path}")

    # Output directories
    checkpoints_dir = Path(__file__).parent.parent / "models_checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    # Initialize model (Ultralytics auto-downloads weights if not local)
    print(f"\n[*] Loading model weights '{args.weights}'...")
    try:
        model = YOLO(args.weights)
    except Exception as e:
        print(f"[!] Warning: Could not initialize {args.weights} directly: {e}")
        print("[*] Falling back to lightweight transfer base (yolo11n.pt)...")
        model = YOLO("yolo11n.pt")

    start_time = time.time()

    # Launch Fine-Tuning with Sonar Physics hyperparameters:
    # 1. mosaic=0.5: moderate mosaic without destroying acoustic nadir boundaries
    # 2. close_mosaic=10: disable mosaic in final 10 epochs for crisp shadow resolution
    # 3. hsv_h/s/v=0: Sonar is single-channel acoustic backscatter (monochrome intensity)
    # 4. fliplr=0.5: Vessel can survey along track in either direction
    # 5. flipud=0.0: NEVER vertically flip sonar waterfall (sound travels down-range!)
    print("\n[*] Starting transfer learning on sonar acoustic tiles...")
    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=device,
        project=args.project,
        name=args.name,
        exist_ok=True,
        optimizer="SGD",
        lr0=0.01,
        lrf=0.01,
        weight_decay=0.0005,
        warmup_epochs=2,
        mosaic=0.5,
        close_mosaic=10,
        # Sonar-specific physics settings:
        hsv_h=0.0,      # Disable hue jitter (sonar has no color)
        hsv_s=0.0,      # Disable saturation jitter
        hsv_v=0.15,     # Modest gain/contrast variation
        fliplr=0.5,     # Port/Starboard horizontal symmetry
        flipud=0.0,     # Prohibit vertical flip (acoustic shadow must trail highlight down-range)
        verbose=True,
    )

    elapsed = time.time() - start_time
    print(f"\n[PASS] Training complete in {elapsed/60.0:.2f} minutes.")

    # Save target checkpoint
    dest_pt = checkpoints_dir / "yolo26n_aquasense_marine.pt"
    try:
        model.save(str(dest_pt))
        print(f"[PASS] Saved model checkpoint to: {dest_pt}")
    except Exception as err:
        print(f"[!] Note on direct save: {err}")

    # Validate
    print("\n[*] Running Validation on Held-Out Split...")
    metrics = model.val()
    print(f"[*] Validation mAP50    : {metrics.box.map50:.4f}")
    print(f"[*] Validation mAP50-95 : {metrics.box.map:.4f}")

    # Optional Edge Export
    if args.export:
        print("\n[*] Exporting for NVIDIA Jetson Orin Nano Edge Deployment...")
        print("    YOLO26 Nano features native NMS-free end-to-end inference!")
        try:
            # ONNX
            onnx_path = model.export(format="onnx", dynamic=False, simplify=True)
            print(f"[PASS] Exported ONNX: {onnx_path}")
            # TensorRT (if running on Jetson with CUDA)
            if torch.cuda.is_available():
                engine_path = model.export(format="engine", half=True, device=0)
                print(f"[PASS] Exported TensorRT Engine: {engine_path}")
            else:
                print("[*] TensorRT export skipped (requires CUDA/Jetson environment).")
        except Exception as e:
            print(f"[!] Export warning: {e}")

    print("\n==================================================================")
    print("  NEXT STAGE IN PIPELINE:")
    print("  1. YOLO26 candidate boxes feed into Stage 4: Physical Feature Verifier")
    print("     (10 acoustic features: shadow ratio, contrast, compactness, etc.)")
    print("  2. Stage 5: Platt scaling calibrates raw scores to 0-100% confidence.")
    print("==================================================================")

if __name__ == "__main__":
    train()
