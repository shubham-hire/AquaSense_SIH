from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_render_blueprint_uses_docker_and_persistent_data_mount():
    config = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "runtime: docker" in config
    assert "dockerfilePath: ./Dockerfile" in config
    assert "healthCheckPath: /health" in config
    assert "mountPath: /data" in config
    assert "AQUASENSE_DATA_DIR" in config
    assert "value: /data" in config
    assert 'value: "1"' in config
    assert "startCommand:" not in config


def test_docker_startup_seeds_mounted_disk_before_model_preflight():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    seed = "COPY best.pt /app/model-seed/best.pt"
    copy_to_disk = "cp -f /app/model-seed/best.pt /data/models/best.pt"
    preflight = "python -m app.preflight"
    server = "exec uvicorn app.main:app"
    assert seed in dockerfile
    assert dockerfile.index(copy_to_disk) < dockerfile.index(preflight)
    assert dockerfile.index(preflight) < dockerfile.index(server)
    assert "AQUASENSE_BATCH_SIZE=1" in dockerfile
    assert "COPY best.pt /data/models/best.pt" not in dockerfile
