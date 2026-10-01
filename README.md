# OceanAid

**AI-powered underwater marine debris and anomaly detection for side-scan sonar — built for shipboard, offline-first use.**
*Smart India Hackathon 2026 · Problem Statement 26057 · Theme: Disaster Management · Ministry of Earth Sciences (MoES) / NIOT*

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/Python-3.11%2B-blue" />
  <img alt="node" src="https://img.shields.io/badge/Node.js-20%20%7C%2022-brightgreen" />
  <img alt="fastapi" src="https://img.shields.io/badge/FastAPI-async%20API-009688" />
  <img alt="react" src="https://img.shields.io/badge/React%2019%20·%20Vite%20·%20Three.js-web%20console-61dafb" />
</p>

---

## What is OceanAid?

OceanAid turns raw side-scan sonar (SSS) data into an actionable survey product: it ingests industry sonar files, runs tiled YOLO detection over the waterfall, and presents contacts on a live map, a 3D seabed twin, and a full-screen waterfall viewer — closing a real gap in the operational workflow used by marine research and disaster-management agencies.

**Detected classes (7):** `shipwreck`, `submarine_pipeline`, `cylinder`, `ghost_net`, `ghost_pot_trap`, `plastic_debris`, `metal_debris`

### Key features

- **Multi-format ingestion** — `.xtf`, `.jsf`, `.sl2`, GeoTIFF, PNG and JPEG, with per-ping navigation preserved for georeferencing.
- **Tiled, batched YOLO26 inference** — adapter-based runtime (CPU/GPU/ONNX), operating on a strict seven-class model contract.
- **Live processing stream** — async processing with WebSocket progress events (stage updates, per-detection confirmations, terminal status) and reconnectable state.
- **Operator console** — 4-quadrant workspace with caliper measurements, streaming map pin drops, a detection queue, and a refusal strip.
- **Executive summary** — KPI deck, map with MPA geofences, and one-click exports of `report.json`, `report.csv`, GIS GeoJSON, and printable hydrographic briefs.
- **Dual-mode object representation** — bounding boxes with real-world metre dimensions plus polygon masks when the checkpoint provides segmentation output.

### Scientific honesty invariants

OceanAid is deliberately conservative about what it claims. These invariants are enforced by code and block bad output rather than merely warning about it:

- **No fabricated coordinates** — navigation metadata must be present and valid in the source sonar record, or detections are reported as *unlocated* with `null` coordinates.
- **No silent failures** — if the model cannot be loaded or an inference batch fails, processing emits a terminal *failed* event instead of an empty-but-successful result.
- **Calibration disclosed** — production detections are explicitly marked `calibrated: false`; the offline calibration/verifier experiment is not presented as an active runtime stage.
- **Verified checkpoint** — the bundled `best.pt` is checked at startup against its SHA-256 and class mapping and will refuse to run otherwise.

---

## How it works

```
 Sonar file (.xtf/.jsf/.sl2)  ──▶  Parse & QC (per-ping nav + integrity checks)
        │
        ▼
 Waterfall render (port/starboard channels)
        │
        ▼
 Tiled YOLO26 inference (thresholds + tile-size honoured)
        │
        ▼
 Post-processing (class contract, coordinates only with valid fixes)
        │
        ▼
 SQLite survey store ──▶ WebSocket stream ──▶ Operator console + exec summary
        │
        ▼
 Reports: report.json · report.csv · GeoJSON · PDF brief
```

---

## Screens & routes

| Route | View | What you'll find |
|---|---|---|
| `/` | Intro landing | Product introduction and entry to the ingestion workspace |
| `/ingest` | Upload page | Sonar upload card (`.xtf`, `.jsf`, `.sl2`, GeoTIFF, PNG, JPEG) and processing launch |
| `/surveys/:id/console` | Operator console | 4-quadrant workspace: waterfall with calipers, 3D digital twin, live map, detection queue, refusal strip |
| `/surveys/:id/summary` | Executive summary | KPI deck, 2D map with MPA geofences, PS-compliant report downloads |
| `/surveys/:id/waterfall` | Waterfall view | Full-screen waterfall: 4 LUT colormaps, acoustic calipers, DSP toggle |
| `/surveys/:id/twin` | Digital twin | 3D seabed bathymetry with bounded orbit camera and threat beacons |
| `/surveys/:id/detections/:d` | Detection detail | Crop viewer with polygon/box toggle, verifier evidence, calibration disclosure, operator review |
| `/surveys/:id/ablations` | Ablation panel | Historical/offline ablation records — explicitly not live runtime metrics |
| `/settings/calibration` | Calibration status | Model checkpoint register with Platt-scaling splits and verification dates |

---

## Getting started

### Prerequisites

| Component | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| npm | 10+ |

### Quickstart (local, recommended)

OceanAid is designed to run entirely on your machine — no cloud services required. Database, sonar artefacts, reports, and inference all stay local, making the stack suitable for shipboard use where uplink cannot be assumed.

```bash
# One-time setup
python3 -m pip install -r backend/requirements.txt
npm install --legacy-peer-deps

# Verify the checkpoint checksum, class mapping, and inference runtime — without starting anything
python3 scripts/run_local.py --check

# Start the API and the web console together
python3 scripts/run_local.py
```

You're all set:

- **Web console** → [http://localhost:3000](http://localhost:3000)
- **API** → [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **API docs (OpenAPI)** → [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Useful flags: `--backend` starts only the API; `--port <n>` changes the API port. Press `Ctrl+C` to stop everything. The Vite dev server proxies `/api` to the backend, so no cross-origin setup is needed in local development.

The runner also sets `YOLO_AUTOINSTALL=false`, so the inference stack can never silently download or install anything mid-survey.

### Running the tests

```bash
# Backend and model pipeline tests
python3 -m pytest backend/tests

# Evaluation tooling tests
python3 -m pytest evaluation
```

### Using a different checkpoint

The verified checkpoint ships as [`best.pt`](best.pt) and is used automatically. To preview another model without touching the bundled file:

```bash
export AQUASENSE_MODEL_PATH=/absolute/path/to/best.pt
```

For embedded deployments (Jetson, Docker volume), drop the checkpoint at `/data/models/best.pt`; the Docker image seeds this path from the committed file before preflight. To export a TensorRT build for Jetson:

```bash
python3 scripts/export_jetson_tensorrt.py
```

### Verifying the checkpoint manually

```bash
sha256sum best.pt
# → 342954fdd4ef6a24b89797f68dbeda8ffd9180b1cc7f7f291324c5cee5898f53
```

---

## Configuration

Environment variables are documented in [`.env.example`](.env.example). Key names:

| Variable | Scope | Purpose |
|---|---|---|
| `AQUASENSE_MODEL_PATH` | backend | Absolute path to the YOLO checkpoint |
| `AQUASENSE_MODEL_SHA256` | backend | Expected checkpoint checksum (enforced at startup) |
| `AQUASENSE_DEVICE`, `AQUASENSE_CONF_THRESH`, `AQUASENSE_IOU_THRESH` | backend | Inference controls |
| `AQUASENSE_TILE_SIZE`, `AQUASENSE_BATCH_SIZE` | backend | Tiling / batching controls |
| `OCEANAID_API_KEY` | backend | Optional shared key for hosted deployments |
| `OCEANAID_CORS_ORIGINS` | backend | Additional allowed CORS origins (comma-separated) |
| `VITE_API_BASE_URL` | frontend | Public base URL of a separately deployed API |
| `VITE_WS_BASE_URL` | frontend | Optional URL when WebSocket service lives elsewhere |
| `VITE_OCEANAID_API_KEY` | frontend | Shared access key (embedded in the browser bundle) |
| `VITE_CARTO_API_KEY` | frontend | Basemap tile key (avoids watermarks) |

---

## Frontend-only development

To work on the UI without the API:

```bash
npm run dev      # Vite dev server on port 3000
npm run build    # Production build (tsc + Vite)
npm run lint     # Type check
```

---

## Repository layout

```
.
├── backend/            # FastAPI service (ingestion, processing, streaming, reports)
│   ├── app/            # detector.py, pipeline.py, xtf/vendor format parsers, taxonomy, schemas
│   └── tests/          # Unit, end-to-end (API + serving), and model pipeline tests
├── src/                # React/Tailwind web console (components grouped by feature)
├── evaluation/         # Offline evaluation tooling: metrics, calibration, dataset splits
├── scripts/            # run_local.py, live-backend verification, TensorRT export, YO26 training
├── configs/            # Dataset configuration for YOLO training
├── models_checkpoints/ # Alternate checkpoints (incl. ONNX export of the bundled model)
├── best.pt             # Verified YOLO checkpoint (in-repo, checksum-pinned)
├── .env.example        # Documented environment variables
├── Dockerfile, render.yaml, fly.toml, docker-compose.yml, vercel.json, Procfile
└── .github/workflows/  # CI: model smoke + backend tests
```

---

## Deployment

Hosting is a convenience for sharing a link, never a requirement — the local path above is the primary way to run OceanAid, and nothing in the processing path depends on a hosted service.

For teams that *do* want a hosted instance, the repo ships with `Dockerfile`, `render.yaml`, `docker-compose.yml`, `fly.toml` and `vercel.json`:

1. **Deploy the backend** on a persistent Python (or Docker) host — it maintains SQLite state, runs model inference, and serves the WebSocket detection stream, so it cannot be a static site. Point it at `/data/models/best.pt` on a mounted persistent volume if you're not sending the checkpoint with the image.
2. **Deploy the Vite build** to Vercel or a similar CDN. `vercel.json` rewrites SPA routes so deep links (e.g. `/surveys/123/console`) load correctly.
3. **Connect them:** set `VITE_API_BASE_URL` to the deployed API origin; set `OCEANAID_CORS_ORIGINS` on the backend to the app URL.
4. **Optional access control:** with `OCEANAID_API_KEY` set on the backend, all `/v1/*` routes require the key on HTTP (via `X-API-Key`) and WebSocket connections (via `api_key`). Adding `VITE_OCEANAID_API_KEY` enables the shared-key gate in the web console for a trusted group — useful for SIH judging or private demos, since it's access control, not per-user identity.
5. **Restart carefully:** hosted restarts wipe non-persistent files. Use a mounted volume for the SQLite DB and drop `best.pt` at `/data/models/best.pt`.

⚠️ **Free-tier caveat:** a free hosting tier is fine for a quick demo, but expect a cold start on the first request, constrained CPU/memory for inference, and no persistent state unless you attach a volume.

---

## Further documentation

| Document | Contents |
|---|---|
| [`MODEL_INTEGRATION.md`](MODEL_INTEGRATION.md) | Checkpoint integration details and verification steps |
| [`backend/README.md`](backend/README.md) | XTF/JSF/SL2 parsing, stream behaviour, and refusal semantics |
| [`AquaSense_PRD_Architecture.md`](AquaSense_PRD_Architecture.md) | Product requirements and architecture |
| [`AquaSense_Frontend_Architecture.md`](AquaSense_Frontend_Architecture.md) | Web console architecture |
| [`AquaSense_Reuse_Extraction_Guide.md`](AquaSense_Reuse_Extraction_Guide.md) | Reusing OceanAid modules in other projects |
| [`evaluation/`](evaluation/) | Offline evaluation and reporting tooling |

---

## CI

GitHub Actions runs model and backend tests on every PR or push touching the model, backend, or deployment config:

- **Model smoke test** — verifies the `best.pt` checksum, installs the runtime, and runs an end-to-end CPU inference test.
- **Backend suite** — runs the standard `pytest backend/tests` set with the model deliberately *unavailable*, exercising the refusal and failure paths.

See [`model-smoke-test.yml`](.github/workflows/model-smoke-test.yml) for the full pipeline.

---

## License

Licensed under **AGPL-3.0** — see [`LICENSE`](LICENSE). This covers application code, the bundled `best.pt` checkpoint (recorded as AGPL-3.0 in `MODEL_INTEGRATION.md`), and use with the `ultralytics` runtime. SIH 2026 submission use coordinated with MoES / NIOT.

---

<p align="center">
  <sub>Built for SIH 2026 · PS ID 26057 · Automated Underwater Marine Debris &amp; Anomaly Detection — MoES / NIOT</sub>
</p>
