# AquaSense — AI-Powered Automated Underwater Marine Debris & Anomaly Detection System
### Ministry of Earth Sciences (MoES) / National Institute of Ocean Technology (NIOT)
**Smart India Hackathon 2026 | Problem Statement 26057 | Category: Software | Theme: Disaster Management**

---

## Overview

AquaSense is an edge-first, AI-powered platform for detecting marine debris, ghost fishing nets (ALDFG), shipwrecks, and subsea hazards in side-scan sonar (SSS) imagery. Grounded in research and Indian Ocean hydrographic operations (ORV Sagar Nidhi / Samudrayaan Deep Ocean Mission), AquaSense combines high visual fidelity with strict scientific honesty:
- **YOLO26 Nano (`yolo26n` / `yolo26n-seg`) Backbone**: NMS-free end-to-end inference and Small-Target-Aware Label Assignment (STAL) delivering sub-20ms per-tile latency on NVIDIA Jetson Orin Nano.
- **Zero hardcoded benchmarks**: every claimed metric is re-computable live.
- **Structural refusal invariants**: missing navigation metadata outputs `null` coordinates and displays as unlocated rather than fabricating positions.
- **10-Feature Learned Physical Verifier**: +30.4% precision gain by filtering acoustic shadow and reverberation artifacts.
- **Dual-mode object representation**: bounding boxes with real-world dimensions (`width_m`, `height_m`) for rigid debris **plus pixel-level polygon segmentation masks** for irregular entangled nets.
- **Official PS 26057 Reporting**: one-click structured export of `report.json` and `report.csv`, GIS GeoJSON, and printable hydrographic briefs.

---

## Architecture & Documentation

- [`AquaSense_PRD_Architecture.md`](./AquaSense_PRD_Architecture.md): Complete Product Requirements & Technical Architecture (v1.1 compliant with official PS 26057).
- [`AquaSense_Frontend_Architecture.md`](./AquaSense_Frontend_Architecture.md): Component hierarchy, route map, state management, and design tokens.
- [`AquaSense_Reuse_Extraction_Guide.md`](./AquaSense_Reuse_Extraction_Guide.md): Teardown extraction checklist from AQUA-SHIELD and EchoPulse.

---

## Route Map

| Route | View | Description |
|---|---|---|
| `/` | `LandingPage` | Sonar upload card (`.xtf`, `.jsf`, `.sl2`, GeoTIFF), sample missions, and architectural pillars |
| `/surveys/:id/console` | `OperatorConsole` | 4-quadrant workspace: Waterfall with calipers, 3D Digital Twin, Live Map with streaming pin drops, Detection Queue, and Refusal Strip |
| `/surveys/:id/summary` | `ExecutiveSummary` | Commander deck: KPI cards, 2D Map with MPA geofences, and PS-compliant report downloads |
| `/surveys/:id/waterfall` | `SonarWaterfallView` | Dedicated full-screen waterfall with 4 LUT colormaps, acoustic calipers, and DSP toggle |
| `/surveys/:id/twin` | `DigitalTwinView` | Dedicated 3D seabed bathymetry with bounded orbit camera and instanced threat beacons |
| `/surveys/:id/detections/:d` | `DetectionDetailPage` | Image crop with polygon mask/box toggle, 10-feature verifier table + L2 weights, and rejected crops audit gallery |
| `/surveys/:id/ablations` | `AblationPanel` | Recharts before/after bar charts for CLAHE drop (-72%), Autoencoder chance level (0.501), and decision captions |
| `/settings/calibration` | `CalibrationStatusPage` | Model checkpoint register detailing Platt scaling splits and verification dates |

---

## Quickstart

### Prerequisites
- Node.js v20+ / v22+
- npm v10+

### Installation & Development
```bash
# Install dependencies
npm install --legacy-peer-deps

# Start Vite dev server on port 3000
npm run dev

# Build for production
npm run build
```

Open [http://localhost:3000](http://localhost:3000) in your browser.
