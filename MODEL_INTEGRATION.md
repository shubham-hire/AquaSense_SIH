# AquaSense `best.pt` integration

The backend now uses the supplied Ultralytics YOLO26 detection checkpoint whenever it is available. The heuristic pipeline remains only as an explicitly labelled fallback when the checkpoint or inference runtime cannot be loaded.

## Verified checkpoint metadata

- Ultralytics checkpoint version: `8.4.153`
- Task: object detection
- Architecture source: `yolo26n.yaml`
- SHA-256: `342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53`
- License recorded in checkpoint: AGPL-3.0
- Classes, in model order:
  1. `shipwreck`
  2. `submarine_pipeline`
  3. `cylinder`
  4. `ghost_net`
  5. `ghost_pot_trap`
  6. `plastic_debris`
  7. `metal_debris`

## Place the model

The binary checkpoint is intentionally not included in this pull request. Put the supplied `best.pt` in one of these locations:

### Local development

```bash
mkdir -p models_checkpoints
cp /path/to/best.pt models_checkpoints/best.pt
```

Alternatively, set an absolute path:

```bash
export AQUASENSE_MODEL_PATH=/absolute/path/to/best.pt
```

### Docker, Render, or Fly.io

Store the checkpoint on the persistent volume at:

```text
/data/models/best.pt
```

The Docker configuration uses that path by default. For Render, use `/var/data/models/best.pt` because the configured persistent disk is mounted at `/var/data`.

## Verify the file

```bash
sha256sum /path/to/best.pt
```

Expected result:

```text
342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53
```

## Run

```bash
pip install -r backend/requirements.txt
AQUASENSE_MODEL_PATH=/absolute/path/to/best.pt \
  python3 -m uvicorn backend.app.main:app --reload --port 8000
```

Check `/health` and then ingest and process an image or supported sonar file.

## Scientific-status note

The checkpoint is not assumed to be calibrated. Detections remain `calibrated: false`, and the code does not fabricate physical-verifier features. Navigation coordinates are emitted only when the source sonar record contains a valid fix.
