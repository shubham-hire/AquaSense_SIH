#!/usr/bin/env bash
# AquaSense: Package Training Bundle for External GPU PC / Google Colab
set -e

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_ZIP="$WORKSPACE_DIR/aquasense_training_bundle.zip"
TEMP_DIR="$WORKSPACE_DIR/temp_training_bundle"

echo "========================================================"
echo "  AQUASENSE: PACKAGING TRAINING BUNDLE FOR EXTERNAL PC  "
echo "========================================================"
echo "[*] Workspace: $WORKSPACE_DIR"

rm -rf "$TEMP_DIR" "$OUTPUT_ZIP"
mkdir -p "$TEMP_DIR/data"

echo "[*] Copying curated sonar dataset (Echo/data/yolo_sonar_dataset)..."
cp -r "$WORKSPACE_DIR/Echo/data/yolo_sonar_dataset" "$TEMP_DIR/data/"

echo "[*] Copying training script and configs..."
cp "$WORKSPACE_DIR/Main/scripts/train_yolo26_sonar.py" "$TEMP_DIR/"
cp "$WORKSPACE_DIR/Main/configs/sonar_debris_yolo26.yaml" "$TEMP_DIR/"

# Update path inside the yaml for the standalone bundle
sed -i '' 's|path: ../Echo/data/yolo_sonar_dataset|path: ./data/yolo_sonar_dataset|g' "$TEMP_DIR/sonar_debris_yolo26.yaml" 2>/dev/null || \
sed -i 's|path: ../Echo/data/yolo_sonar_dataset|path: ./data/yolo_sonar_dataset|g' "$TEMP_DIR/sonar_debris_yolo26.yaml"

echo "[*] Writing quick-start runner instructions..."
cat << 'EOF' > "$TEMP_DIR/README_RUN_TRAINING.txt"
======================================================
  AQUASENSE YOLO26 STANDALONE TRAINING INSTRUCTIONS
======================================================

1. Requirements (run once on your GPU PC):
   pip install ultralytics torch torchvision

2. Run Training:
   python train_yolo26_sonar.py --data sonar_debris_yolo26.yaml --weights yolo26n.pt --epochs 50 --batch 16

   (For segmentation masks on nets/ropes, use --weights yolo26n-seg.pt)

3. When training finishes:
   Your trained model will be at:
   runs/detect/yolo26_aquasense_sonar/weights/best.pt (~6 MB)

4. Bring it back:
   Copy 'best.pt' back to your main PC and put it at:
   Main/models_checkpoints/yolo26n_aquasense_marine.pt
======================================================
EOF

echo "[*] Compressing bundle into zip..."
cd "$WORKSPACE_DIR"
zip -q -r "$OUTPUT_ZIP" temp_training_bundle

rm -rf "$TEMP_DIR"
echo "[PASS] Successfully generated: $OUTPUT_ZIP"
ls -lh "$OUTPUT_ZIP"
echo "========================================================"
echo "Ready! You can copy '$OUTPUT_ZIP' to your other PC via USB or Google Drive."
