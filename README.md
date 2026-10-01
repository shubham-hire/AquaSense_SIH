# OceanAid — AI-Powered Automated Underwater Marine Debris & Anomaly Detection System
### Ministry of Earth Sciences (MoES) / National Institute of Ocean Technology (NIOT)
**Smart India Hackathon 2026 | Problem Statement 26057 | Category: Software | Theme: Disaster Management**

---

## Overview

OceanAid is an edge-first, AI-powered platform for detecting marine debris, ghost fishing nets (ALDFG), shipwrecks, and subsea hazards in side-scan sonar (SSS) imagery. Grounded in research and Indian Ocean hydrographic operations (ORV Sagar Nidhi / Samudrayaan Deep Ocean Mission), OceanAid combines high visual fidelity with strict scientific honesty:
- **YOLO26 Nano (`yolo26n` / `yolo26n-seg`) Backbone**: tiled, batched inference with a checked seven-class model contract and CPU/GPU/ONNX adapter paths.
- **Reproducible evaluation tooling**: the `evaluation/` commands recompute model, calibration, and deployment reports; historical UI ablations are explicitly labelled and are not treated as live runtime measurements.
- **Structural refusal invariants**: missing navigation metadata outputs `null` coordinates and displays as unlocated rather than fabricating positions. If the detection model cannot be loaded or inference fails, processing fails loudly instead of inventing detections or reporting a false zero-result success.
- **Honest calibration and verifier status**: current production detections report `calibrated: false`; the offline 10-feature verifier experiment is not presented as an active runtime stage.
- **Dual-mode object representation**: bounding boxes with real-world dimensions (`width_m`, `height_m`) for rigid debris plus polygon masks when the loaded checkpoint actually provides segmentation output.
- **Official PS 26057 Reporting**: one-click structured export of `report.json` and `report.csv`, GIS GeoJSON, and printable hydrographic briefs.

---

## Runs on your machine, with no cloud dependency

OceanAid is designed for shipboard use, where an uplink cannot be assumed. Nothing in the processing path requires a hosted service:

| Concern | Where it lives |
|---|---|
| Detection model | `best.pt`, committed in this repository and verified by SHA-256 at startup |
| Survey database | SQLite file under your local data directory |
| Sonar artifacts and waterfalls | Local filesystem |
| Reports (JSON, CSV, GeoJSON, PDF) | Generated locally on request |
| Map tiles | The only feature that benefits from internet access |

The runner also sets `YOLO_AUTOINSTALL=false`, so the inference stack can never attempt to download or install anything mid-survey.

### Quickstart (local, recommended)

Prerequisites: Python 3.11+, Node.js v20+/v22+, npm v10+.

```bash
# One-time setup
python3 -m pip install -r backend/requirements.txt
npm install --legacy-peer-deps

# Verify the checkpoint checksum, class mapping, and inference runtime without starting anything
python3 scripts/run_local.py --check

# Start the API and the web console together
python3 scripts/run_local.py
```

- Web console: [http://localhost:3000](http://localhost:3000)
- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Use `--backend` to start only the API, and `--port` to serve it elsewhere. Press Ctrl+C to stop everything. The Vite dev server proxies `/api` to the local backend, so the browser never needs an external API origin.

If a prerequisite is missing, the runner refuses to start and names the exact problem rather than failing halfway through a survey.

### Running the tests

```bash
python3 -m pytest backend/tests
python3 -m pytest evaluation
```

---

## Route Map

| Route | View | Description |
|---|---|---|
| `/` | `IntroLanding` | Product introduction and entry point to the ingestion workspace |
| `/ingest` | `LandingPage` | Sonar upload card (`.xtf`, `.jsf`, `.sl2`, GeoTIFF, PNG, or JPEG) and processing launch |
| `/surveys/:id/console` | `OperatorConsole` | 4-quadrant workspace: Waterfall with calipers, 3D Digital Twin, Live Map with streaming pin drops, Detection Queue, and Refusal Strip |
| `/surveys/:id/summary` | `ExecutiveSummary` | Commander deck: KPI cards, 2D Map with MPA geofences, and PS-compliant report downloads |
| `/surveys/:id/waterfall` | `SonarWaterfallView` | Dedicated full-screen waterfall with 4 LUT colormaps, acoustic calipers, and DSP toggle |
| `/surveys/:id/twin` | `DigitalTwinView` | Dedicated 3D seabed bathymetry with bounded orbit camera and instanced threat beacons |
| `/surveys/:id/detections/:d` | `DetectionDetailPage` | Image crop with polygon mask/box toggle, verifier evidence when supplied by the backend, calibration disclosure, and operator review |
| `/surveys/:id/ablations` | `AblationPanel` | Historical/offline ablation records with explicit decision captions; these are not live runtime metrics |
| `/settings/calibration` | `CalibrationStatusPage` | Model checkpoint register detailing Platt scaling splits and verification dates |

---

## Frontend-only development

To work on the UI without the API running:

```bash
npm run dev      # Vite dev server on port 3000
npm run build    # Production build
npm run lint     # Type check
```

---

## Optional: hosted deployment

Hosting is a convenience for sharing a link, not a requirement. The local path above is the primary way to run OceanAid.

The repository includes `Dockerfile`, `render.yaml`, `docker-compose.yml`, and `vercel.json` for teams that want a hosted instance.

1. Deploy the FastAPI service on a persistent Python or Docker host. It processes large sonar uploads, maintains SQLite state, runs model inference, and serves the detection stream, so it cannot be a static asset.
2. Deploy the Vite/React app to Vercel. `vercel.json` ensures direct visits to console, map, and survey routes load the single-page app.
3. In Vercel → Settings → Environment Variables, set `VITE_API_BASE_URL` to the deployed API origin, for example `https://api.example.com`. Do not append `/api`. If the stream service uses another origin, set `VITE_WS_BASE_URL` to its `wss://` URL. See `.env.example` for the expected names.
4. On the API host, set `OCEANAID_CORS_ORIGINS` to your production URL and any preview URL that needs access, comma-separated.
5. For a shared/private deployment, set `OCEANAID_API_KEY` on the API and the same value as `VITE_OCEANAID_API_KEY` in the web build. This enables the built-in shared-key gate for HTTP and WebSocket operations. Because Vite variables are visible to browser users, use this only as access control for a trusted group—not as per-user identity. Internet-facing operational deployments should put the API behind a real identity-aware proxy.

`VITE_API_BASE_URL` is intentionally public and safe to configure in Vercel; it is an endpoint, not a credential. `VITE_OCEANAID_API_KEY` is a shared deployment value and must never be mistaken for a private browser secret.

### Free-tier caveats

A free hosting tier is fine for a quick look, but be aware of what it costs you:

- **No persistent disk**: the SQLite database is wiped on every restart, so surveys, detections, and operator reviews do not survive a redeploy or an idle spin-down.
- **Idle spin-down**: the first request after inactivity pays a cold start for both the container and the model weights.
- **Constrained CPU and memory**: inference on full-resolution sonar is materially slower than on a laptop.

For demonstrations and real survey work, run OceanAid locally: persistent storage, no cold start, and no dependency on a third party.
