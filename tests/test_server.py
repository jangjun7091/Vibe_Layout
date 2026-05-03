from pathlib import Path

from fastapi.testclient import TestClient

from klayout_harness.server import create_app


PROMPT = (
    "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)


def test_server_rejects_unauthorized_request(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))

    response = client.post("/api/layouts", json={"prompt": PROMPT})

    assert response.status_code == 401


def test_server_creates_job_and_serves_artifacts(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))
    headers = {"Authorization": "Bearer secret"}

    response = client.post("/api/layouts", json={"prompt": PROMPT}, headers=headers)

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "completed"
    assert job["validation_passed"]
    job_id = job["job_id"]

    status_response = client.get(f"/api/layouts/{job_id}", headers=headers)
    preview_response = client.get(f"/api/layouts/{job_id}/preview.png", headers=headers)
    gds_response = client.get(f"/api/layouts/{job_id}/layout.gds", headers=headers)

    assert status_response.status_code == 200
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"] == "image/png"
    assert gds_response.status_code == 200
    assert len(gds_response.content) > 0


def test_server_websocket_replays_ordered_events(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))
    headers = {"Authorization": "Bearer secret"}
    job = client.post("/api/layouts", json={"prompt": PROMPT}, headers=headers).json()

    with client.websocket_connect(f"/ws/jobs/{job['job_id']}", headers=headers) as websocket:
        events = [websocket.receive_json()["event"] for _ in range(7)]

    assert events == [
        "semantic_started",
        "semantic_resolved",
        "actuation_started",
        "gds_written",
        "preview_rendered",
        "validation_passed",
        "completed",
    ]
