from pathlib import Path

from fastapi.testclient import TestClient

from klayout_harness.server import create_app


PROMPT = (
    "[Vibe_Layout] $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)


def test_server_rejects_unauthorized_request(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))

    response = client.post("/api/layouts", json={"prompt": PROMPT})

    assert response.status_code == 401


def test_server_serves_viewer_page(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))

    response = client.get("/viewer")

    assert response.status_code == 200
    assert "Vibe Layout Viewer" in response.text
    assert "Generate Layout" in response.text
    assert "Layout Preview" in response.text
    assert "Artifacts" in response.text
    assert "Generated Code" in response.text
    assert "Open KLayout" in response.text
    assert "ctrlKey" in response.text
    assert "[Vibe_Layout]" in response.text
    assert "open_viewer: false" in response.text
    assert "job_id" in response.text


def test_server_creates_job_and_serves_artifacts(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))
    headers = {"Authorization": "Bearer secret"}

    response = client.post("/api/layouts", json={"prompt": PROMPT}, headers=headers)

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "completed"
    assert job["validation_passed"]
    assert "import klayout.db as kdb" in job["python_code"]
    assert "/viewer#job_id=" in job["viewer_url"]
    assert job["viewer_opened"] is False
    job_id = job["job_id"]

    status_response = client.get(f"/api/layouts/{job_id}", headers=headers)
    preview_response = client.get(f"/api/layouts/{job_id}/preview.png", headers=headers)
    gds_response = client.get(f"/api/layouts/{job_id}/layout.gds", headers=headers)

    assert status_response.status_code == 200
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"] == "image/png"
    assert gds_response.status_code == 200
    assert len(gds_response.content) > 0


def test_server_auto_opens_viewer_for_api_job(tmp_path: Path, monkeypatch) -> None:
    opened: dict[str, str] = {}

    def fake_open_viewer_url(url: str) -> dict:
        opened["url"] = url
        return {"opened": True, "url": url}

    monkeypatch.setattr("klayout_harness.server._open_viewer_url", fake_open_viewer_url)
    client = TestClient(
        create_app(
            token="secret",
            jobs_dir=tmp_path,
            auto_open_viewer=True,
            viewer_base_url="http://127.0.0.1:9999",
        )
    )
    headers = {"Authorization": "Bearer secret"}

    response = client.post("/api/layouts", json={"prompt": PROMPT}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["viewer_opened"] is True
    assert response.json()["viewer_url"].startswith("http://127.0.0.1:9999/viewer#job_id=")
    assert opened["url"] == response.json()["viewer_url"]
    assert f"job_id={response.json()['job_id']}" in opened["url"]
    assert "token=secret" in opened["url"]


def test_server_respects_open_viewer_false(tmp_path: Path, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("klayout_harness.server._open_viewer_for_job", lambda *args: opened.append("opened"))
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path, auto_open_viewer=True))
    headers = {"Authorization": "Bearer secret"}

    response = client.post("/api/layouts", json={"prompt": PROMPT, "open_viewer": False}, headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["viewer_opened"] is False
    assert "/viewer#job_id=" in response.json()["viewer_url"]
    assert opened == []


def test_server_fails_job_without_vibe_layout_command(tmp_path: Path) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))
    headers = {"Authorization": "Bearer secret"}

    response = client.post(
        "/api/layouts",
        json={"prompt": "$1mm \\times 1mm$ root cell 'CHIP_ROOT'."},
        headers=headers,
    )

    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "failed"
    assert not job["validation_passed"]
    assert job["gds_path"] is None
    assert "[Vibe_Layout]" in job["findings"][0]["message"]


def test_server_opens_job_in_klayout(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(create_app(token="secret", jobs_dir=tmp_path))
    headers = {"Authorization": "Bearer secret"}
    job = client.post("/api/layouts", json={"prompt": PROMPT}, headers=headers).json()
    opened: dict[str, str] = {}

    def fake_open(path: Path) -> dict:
        opened["path"] = str(path)
        return {"opened": True, "method": "test", "path": str(path)}

    monkeypatch.setattr("klayout_harness.server._open_gds_in_klayout", fake_open)

    response = client.post(f"/api/layouts/{job['job_id']}/open-klayout", headers=headers)

    assert response.status_code == 200
    assert response.json()["opened"] is True
    assert opened["path"].endswith(".gds")


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
