from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

from .jobs import LayoutJobRunner


class LayoutRequest(BaseModel):
    prompt: str
    open_gui: bool = False


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.setdefault(job_id, []).append(websocket)

    def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        sockets = self.active.get(job_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
        if not sockets and job_id in self.active:
            del self.active[job_id]

    async def broadcast(self, job_id: str, event: dict) -> None:
        for websocket in list(self.active.get(job_id, [])):
            await websocket.send_json(event)


def create_app(token: str | None = None, jobs_dir: str | Path = "build/jobs") -> FastAPI:
    auth_token = token or os.environ.get("VIBE_LAYOUT_TOKEN") or secrets.token_urlsafe(24)
    runner = LayoutJobRunner(jobs_dir)
    manager = ConnectionManager()
    app = FastAPI(title="Vibe Layout Realtime Server")
    app.state.vibe_layout_token = auth_token
    app.state.vibe_layout_runner = runner
    app.state.vibe_layout_manager = manager

    def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
        if authorization != f"Bearer {auth_token}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer() -> str:
        return VIEWER_HTML

    @app.post("/api/layouts", dependencies=[Depends(require_auth)])
    def create_layout(request: LayoutRequest) -> dict:
        job = runner.run(request.prompt)
        return job.to_dict()

    @app.get("/api/layouts/{job_id}", dependencies=[Depends(require_auth)])
    def get_layout(job_id: str) -> dict:
        job = runner.load(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.to_dict()

    @app.get("/api/layouts/{job_id}/preview.png", dependencies=[Depends(require_auth)])
    def get_preview(job_id: str) -> FileResponse:
        job = runner.load(job_id)
        if job is None or job.preview_path is None:
            raise HTTPException(status_code=404, detail="Preview not found")
        return FileResponse(job.preview_path, media_type="image/png")

    @app.get("/api/layouts/{job_id}/layout.gds", dependencies=[Depends(require_auth)])
    def get_gds(job_id: str) -> FileResponse:
        job = runner.load(job_id)
        if job is None or job.gds_path is None:
            raise HTTPException(status_code=404, detail="GDS not found")
        return FileResponse(job.gds_path, media_type="application/octet-stream", filename=Path(job.gds_path).name)

    @app.websocket("/ws/jobs/{job_id}")
    async def websocket_job(websocket: WebSocket, job_id: str) -> None:
        ws_token = websocket.headers.get("authorization")
        if ws_token != f"Bearer {auth_token}":
            await websocket.close(code=1008)
            return
        await manager.connect(job_id, websocket)
        try:
            job = runner.load(job_id)
            if job is not None:
                for event in job.events:
                    await websocket.send_json(event)
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(job_id, websocket)

    return app


VIEWER_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vibe Layout Viewer</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1d2430;
      --muted: #617084;
      --line: #d8dee8;
      --panel: #f7f9fc;
      --accent: #1669d8;
      --bad: #b42318;
      --ok: #067647;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #fff;
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      min-height: 100vh;
    }
    aside {
      border-right: 1px solid var(--line);
      background: var(--panel);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    main {
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }
    h1 {
      font-size: 18px;
      margin: 0 0 4px;
      letter-spacing: 0;
    }
    label {
      font-size: 12px;
      color: var(--muted);
      display: block;
      margin-bottom: 4px;
    }
    input, textarea, button {
      font: inherit;
    }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      background: #fff;
      color: var(--ink);
    }
    textarea {
      min-height: 160px;
      resize: vertical;
      line-height: 1.4;
    }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 9px 11px;
      cursor: pointer;
    }
    button.secondary {
      background: #fff;
      color: var(--accent);
    }
    button:disabled {
      opacity: .55;
      cursor: not-allowed;
    }
    .row {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .row > * { flex: 1; }
    .toolbar {
      border-bottom: 1px solid var(--line);
      padding: 10px 14px;
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }
    .status {
      margin-left: auto;
      font-size: 13px;
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .viewport {
      overflow: auto;
      background:
        linear-gradient(45deg, #f2f4f7 25%, transparent 25%),
        linear-gradient(-45deg, #f2f4f7 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, #f2f4f7 75%),
        linear-gradient(-45deg, transparent 75%, #f2f4f7 75%);
      background-size: 28px 28px;
      background-position: 0 0, 0 14px, 14px -14px, -14px 0;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .canvas-shell {
      min-width: 240px;
      min-height: 240px;
      display: grid;
      place-items: center;
    }
    img {
      transform-origin: center center;
      max-width: none;
      border: 1px solid var(--line);
      background: #fff;
      box-shadow: 0 8px 24px rgba(20, 30, 45, .12);
    }
    pre {
      margin: 0;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      min-height: 120px;
      max-height: 220px;
      overflow: auto;
      font-size: 12px;
      line-height: 1.35;
      white-space: pre-wrap;
    }
    .ok { color: var(--ok); }
    .bad { color: var(--bad); }
    @media (max-width: 900px) {
      body { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <aside>
    <div>
      <h1>Vibe Layout Viewer</h1>
      <div class="status" id="serverHint">Local realtime preview</div>
    </div>
    <div>
      <label for="token">Bearer token</label>
      <input id="token" type="password" autocomplete="off" placeholder="VIBE_LAYOUT_TOKEN">
    </div>
    <div>
      <label for="prompt">Layout prompt</label>
      <textarea id="prompt">Vibe_Layout, 양자 홀 효과(Quantum Hall Effect) 측정을 위한 Standard 6-terminal Hall Bar 레이아웃을 설계해줘. 메인 채널의 폭은 $50\mu m$로 하고, 전압 리드(Voltage leads)는 신호 간섭을 줄이기 위해 $10\mu m$ 폭으로 아주 얇게 설계해. 외부 측정 장비와 연결하기 위해 각 리드 끝에는 $200\mu m \times 200\mu m$ 크기의 본딩 패드(Bonding Pad)를 추가해줘. 전체 소자는 (1, 0) 레이어에 배치해</textarea>
    </div>
    <button id="generate">Generate</button>
    <div class="row">
      <button id="downloadGds" class="secondary" disabled>GDS</button>
      <button id="downloadPng" class="secondary" disabled>PNG</button>
    </div>
    <div>
      <label>Job</label>
      <pre id="jobLog">No job yet.</pre>
    </div>
  </aside>
  <main>
    <div class="toolbar">
      <button class="secondary" id="zoomOut">−</button>
      <button class="secondary" id="zoomReset">100%</button>
      <button class="secondary" id="zoomIn">+</button>
      <span class="status" id="statusText">Ready</span>
    </div>
    <div class="viewport">
      <div class="canvas-shell">
        <img id="preview" alt="Generated layout preview" hidden>
      </div>
    </div>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    const promptInput = document.getElementById("prompt");
    const generateButton = document.getElementById("generate");
    const statusText = document.getElementById("statusText");
    const jobLog = document.getElementById("jobLog");
    const preview = document.getElementById("preview");
    const downloadGds = document.getElementById("downloadGds");
    const downloadPng = document.getElementById("downloadPng");
    let currentJob = null;
    let currentPreviewBlobUrl = null;
    let zoom = 1;

    function authHeaders() {
      const token = tokenInput.value.trim();
      return token ? { "Authorization": `Bearer ${token}` } : {};
    }

    function setStatus(text, failed = false) {
      statusText.textContent = text;
      statusText.className = failed ? "status bad" : "status";
    }

    async function fetchArtifactBlob(job, artifact) {
      const response = await fetch(`/api/layouts/${job.job_id}/${artifact}`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`${response.status} ${await response.text()}`);
      }
      return await response.blob();
    }

    async function renderJob(job) {
      currentJob = job;
      const summary = {
        job_id: job.job_id,
        status: job.status,
        validation_passed: job.validation_passed,
        spec: job.spec,
        findings: job.findings,
      };
      jobLog.textContent = JSON.stringify(summary, null, 2);
      if (job.status === "completed") {
        const previewBlob = await fetchArtifactBlob(job, "preview.png");
        if (currentPreviewBlobUrl) {
          URL.revokeObjectURL(currentPreviewBlobUrl);
        }
        currentPreviewBlobUrl = URL.createObjectURL(previewBlob);
        preview.src = currentPreviewBlobUrl;
        preview.hidden = false;
        downloadPng.disabled = false;
        downloadGds.disabled = false;
        setStatus(`Completed ${job.job_id}`);
      } else {
        setStatus(`Job ${job.status}`, true);
      }
    }

    async function generate() {
      generateButton.disabled = true;
      downloadGds.disabled = true;
      downloadPng.disabled = true;
      preview.hidden = true;
      setStatus("Generating...");
      jobLog.textContent = "Submitting job...";
      try {
        const response = await fetch("/api/layouts", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ prompt: promptInput.value, open_gui: false }),
        });
        if (!response.ok) {
          throw new Error(`${response.status} ${await response.text()}`);
        }
        await renderJob(await response.json());
      } catch (error) {
        jobLog.textContent = String(error);
        setStatus("Failed", true);
      } finally {
        generateButton.disabled = false;
      }
    }

    function applyZoom() {
      preview.style.transform = `scale(${zoom})`;
      document.getElementById("zoomReset").textContent = `${Math.round(zoom * 100)}%`;
    }

    document.getElementById("zoomIn").addEventListener("click", () => { zoom = Math.min(4, zoom * 1.25); applyZoom(); });
    document.getElementById("zoomOut").addEventListener("click", () => { zoom = Math.max(.25, zoom / 1.25); applyZoom(); });
    document.getElementById("zoomReset").addEventListener("click", () => { zoom = 1; applyZoom(); });
    generateButton.addEventListener("click", generate);
    async function downloadArtifact(artifact, filename) {
      if (!currentJob) return;
      const blob = await fetchArtifactBlob(currentJob, artifact);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }
    downloadGds.addEventListener("click", () => downloadArtifact("layout.gds", "layout.gds"));
    downloadPng.addEventListener("click", () => downloadArtifact("preview.png", "preview.png"));
    applyZoom();
  </script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Vibe Layout realtime server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--jobs-dir", default="build/jobs")
    parser.add_argument("--token", default=os.environ.get("VIBE_LAYOUT_TOKEN"))
    args = parser.parse_args()

    token = args.token or secrets.token_urlsafe(24)
    print(f"vibe_layout_server=http://{args.host}:{args.port}")
    print(f"vibe_layout_token={token}")
    uvicorn.run(create_app(token=token, jobs_dir=args.jobs_dir), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
