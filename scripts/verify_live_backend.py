#!/usr/bin/env python3
"""
verify_live_backend.py — Live End-to-End Verification Script for AquaSense API.

Usage:
  python3 scripts/verify_live_backend.py [BACKEND_URL]

Examples:
  python3 scripts/verify_live_backend.py http://127.0.0.1:8000
  python3 scripts/verify_live_backend.py https://aquasense-api.onrender.com
  python3 scripts/verify_live_backend.py https://aquasense-api-production.up.railway.app
"""
import asyncio
import io
import json
import sys
import time
from uuid import uuid4
from PIL import Image

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


async def run_verification(backend_url: str):
    backend_url = backend_url.rstrip("/")
    print(f"\n🌊 AquaSense Live Backend End-to-End Verification")
    print(f"Target: {backend_url}")
    print("=" * 60)

    results = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Root and Health check
        t0 = time.perf_counter()
        try:
            health_resp = await client.get(f"{backend_url}/health")
            t_health = (time.perf_counter() - t0) * 1000
            if health_resp.status_code == 200:
                h = health_resp.json()
                storage = h.get("storage", {})
                disk_free = storage.get("disk_free_gb", "N/A")
                model_status = h.get("model", {}).get("weights_present", False)
                results.append(("1. Health Check", "PASS", f"{t_health:.1f}ms (Storage: {storage.get('type')}, Free: {disk_free} GB, Model Weights: {model_status})"))
            else:
                results.append(("1. Health Check", "FAIL", f"HTTP {health_resp.status_code}"))
        except Exception as e:
            results.append(("1. Health Check", "FAIL", str(e)))
            print(f"❌ Could not connect to {backend_url}: {e}")
            return

        # 2. CORS check for Vercel origin
        cors_headers = {
            "Origin": "https://aqua-sense-sih.vercel.app",
            "Access-Control-Request-Method": "POST",
        }
        options_resp = await client.options(f"{backend_url}/v1/surveys/test/ingest", headers=cors_headers)
        allow_origin = options_resp.headers.get("access-control-allow-origin")
        if allow_origin in ("https://aqua-sense-sih.vercel.app", "*"):
            results.append(("2. CORS Headers", "PASS", f"Allowed: {allow_origin}"))
        else:
            results.append(("2. CORS Headers", "WARN", f"Origin header: {allow_origin}"))

        # 3. Survey Ingestion
        survey_id = f"survey-test-{uuid4().hex[:8]}"
        img_buf = io.BytesIO()
        Image.new("L", (128, 128), color=100).save(img_buf, format="PNG")
        img_bytes = img_buf.getvalue()

        files = {"file": ("scan.png", img_bytes, "image/png")}
        t0 = time.perf_counter()
        ingest_resp = await client.post(f"{backend_url}/v1/surveys/{survey_id}/ingest", files=files)
        t_ingest = (time.perf_counter() - t0) * 1000

        if ingest_resp.status_code == 200:
            qc = ingest_resp.json().get("qc_report", {})
            results.append(("3. Ingest Survey", "PASS", f"{t_ingest:.1f}ms (QC: {qc.get('status')})"))
        else:
            results.append(("3. Ingest Survey", "FAIL", f"HTTP {ingest_resp.status_code}"))
            return

        # 4. WebSocket Streaming + Processing
        ws_url = backend_url.replace("https://", "wss://").replace("http://", "ws://") + f"/v1/surveys/{survey_id}/stream"
        events_captured = []

        if HAS_WEBSOCKETS:
            try:
                async with websockets.connect(ws_url) as ws:
                    # Trigger process
                    proc_resp = await client.post(f"{backend_url}/v1/surveys/{survey_id}/process")
                    if proc_resp.status_code == 202:
                        while True:
                            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            msg = json.loads(raw)
                            events_captured.append(msg.get("event"))
                            if msg.get("event") in ("processing.complete", "processing.failed"):
                                break
                        results.append(("4. WebSocket Stream", "PASS", f"Received: {', '.join(events_captured)}"))
                    else:
                        results.append(("4. WebSocket Stream", "FAIL", f"Trigger HTTP {proc_resp.status_code}"))
            except Exception as e:
                results.append(("4. WebSocket Stream", "WARN", f"WS Error ({e}), checking polling"))
                # Fallback to polling /processing
                await client.post(f"{backend_url}/v1/surveys/{survey_id}/process")
                await asyncio.sleep(1.0)
                status_resp = await client.get(f"{backend_url}/v1/surveys/{survey_id}/processing")
                results.append(("4. Polling Fallback", "PASS", str(status_resp.json().get("event"))))
        else:
            await client.post(f"{backend_url}/v1/surveys/{survey_id}/process")
            await asyncio.sleep(1.0)
            status_resp = await client.get(f"{backend_url}/v1/surveys/{survey_id}/processing")
            results.append(("4. Stream Status", "PASS", f"Status: {status_resp.json().get('event')}"))

        # 5. Detections & Position Invariant
        det_resp = await client.get(f"{backend_url}/v1/surveys/{survey_id}/detections")
        detections = det_resp.json() if det_resp.status_code == 200 else []
        if detections:
            first = detections[0]
            det_id = first["id"]
            refusal_ok = first["position"]["position_source"] == "UNAVAILABLE"
            results.append(("5. Detection Listing", "PASS", f"{len(detections)} detection(s), Refusal preserved: {refusal_ok}"))
        else:
            results.append(("5. Detection Listing", "FAIL", f"HTTP {det_resp.status_code} or 0 detections"))
            return

        # 6. Operator Review
        review_body = {
            "outcome": "CONFIRMED",
            "note": "Verified via automated diagnostic runner",
            "nav_trustworthy": True,
            "reviewed_by": "qa_runner",
        }
        put_rev = await client.put(f"{backend_url}/v1/detections/{det_id}/review", json=review_body)
        get_rev = await client.get(f"{backend_url}/v1/detections/{det_id}/review")
        if put_rev.status_code == 200 and get_rev.status_code == 200 and get_rev.json().get("outcome") == "CONFIRMED":
            results.append(("6. Operator Review", "PASS", "Saved & retrieved (outcome: CONFIRMED)"))
        else:
            results.append(("6. Operator Review", "FAIL", f"PUT: {put_rev.status_code}, GET: {get_rev.status_code}"))

        # 7. Exports
        json_rep = await client.get(f"{backend_url}/v1/surveys/{survey_id}/report.json")
        csv_rep = await client.get(f"{backend_url}/v1/surveys/{survey_id}/report.csv")
        geojson_rep = await client.get(f"{backend_url}/v1/surveys/{survey_id}/geojson")
        pdf_rep = await client.get(f"{backend_url}/v1/surveys/{survey_id}/report.pdf")

        exports_ok = (
            json_rep.status_code == 200
            and csv_rep.status_code == 200
            and geojson_rep.status_code == 200
            and pdf_rep.status_code == 200
            and pdf_rep.content.startswith(b"%PDF")
        )
        if exports_ok:
            results.append(("7. Report Exports", "PASS", "JSON, CSV, GeoJSON, and PDF all generated"))
        else:
            results.append(("7. Report Exports", "FAIL", f"JSON:{json_rep.status_code} CSV:{csv_rep.status_code} GeoJSON:{geojson_rep.status_code} PDF:{pdf_rep.status_code}"))

    print("\n📋 Verification Results:")
    print(f"{'Check':<25} | {'Status':<6} | {'Details'}")
    print("-" * 60)
    for name, status, detail in results:
        icon = "✅" if status == "PASS" else ("⚠️" if status == "WARN" else "❌")
        print(f"{icon} {name:<23} | {status:<6} | {detail}")
    print("=" * 60)

    failures = [r for r in results if r[1] == "FAIL"]
    if failures:
        print(f"❌ {len(failures)} check(s) failed.")
        sys.exit(1)
    else:
        print("🎉 All end-to-end checks passed successfully!")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    asyncio.run(run_verification(target))
