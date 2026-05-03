from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
import subprocess
from typing import Annotated
from urllib.parse import quote
import webbrowser

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

from .cli import find_klayout_executable
from .jobs import LayoutJobRunner


class LayoutRequest(BaseModel):
    prompt: str
    open_gui: bool = False
    open_viewer: bool | None = None


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


def create_app(
    token: str | None = None,
    jobs_dir: str | Path = "build/jobs",
    auto_open_viewer: bool = False,
    viewer_base_url: str = "http://127.0.0.1:8765",
) -> FastAPI:
    auth_token = token or os.environ.get("VIBE_LAYOUT_TOKEN") or secrets.token_urlsafe(24)
    runner = LayoutJobRunner(jobs_dir)
    manager = ConnectionManager()
    app = FastAPI(title="Vibe Layout Realtime Server")
    app.state.vibe_layout_token = auth_token
    app.state.vibe_layout_runner = runner
    app.state.vibe_layout_manager = manager
    app.state.vibe_layout_auto_open_viewer = auto_open_viewer
    app.state.vibe_layout_viewer_base_url = viewer_base_url.rstrip("/")

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
        viewer_url = _viewer_url_for_job(app.state.vibe_layout_viewer_base_url, job.job_id, auth_token)
        response = job.to_dict()
        response["viewer_url"] = viewer_url
        response["viewer_opened"] = False
        response["agent_action"] = _agent_action_for_viewer(viewer_url)
        should_open_viewer = request.open_viewer if request.open_viewer is not None else auto_open_viewer
        if should_open_viewer and job.status == "completed":
            response["viewer_opened"] = _open_viewer_url(viewer_url)["opened"]
        return response

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

    @app.post("/api/layouts/{job_id}/open-klayout", dependencies=[Depends(require_auth)])
    def open_klayout(job_id: str) -> dict:
        job = runner.load(job_id)
        if job is None or job.gds_path is None:
            raise HTTPException(status_code=404, detail="GDS not found")
        return _open_gds_in_klayout(Path(job.gds_path))

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


def _open_gds_in_klayout(path: Path) -> dict:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="GDS file not found")

    executable = find_klayout_executable()
    if executable is not None:
        subprocess.Popen([str(executable), str(path)])
        return {"opened": True, "method": str(executable), "path": str(path)}

    if os.name == "nt":
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            return {"opened": True, "method": "windows-file-association", "path": str(path)}
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to open KLayout: {exc}") from exc

    raise HTTPException(
        status_code=404,
        detail="KLayout executable not found. Set KLAYOUT_EXE or add klayout to PATH.",
    )


def _open_viewer_for_job(base_url: str, job_id: str, token: str) -> dict:
    return _open_viewer_url(_viewer_url_for_job(base_url, job_id, token))


def _viewer_url_for_job(base_url: str, job_id: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/viewer#job_id={quote(job_id)}&token={quote(token)}"


def _agent_action_for_viewer(viewer_url: str) -> dict:
    return {
        "type": "open_internal_browser",
        "target": "vibe_layout_viewer",
        "url": viewer_url,
        "instruction": (
            "Open this URL inside the active agent browser surface, such as the Codex in-app browser "
            "or Claude Code browser preview. Do not open preview.png, generated standalone HTML files, "
            "or file:// artifacts as the primary result view."
        ),
    }


def _open_viewer_url(url: str) -> dict:
    opened = webbrowser.open(url, new=2)
    return {"opened": opened, "url": url}


VIEWER_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vibe Layout Viewer</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172033;
      --muted: #667085;
      --line: #d0d7e2;
      --panel: #f7f9fc;
      --panel-strong: #eef3f8;
      --accent: #1769d1;
      --accent-ink: #0f4d9d;
      --bad: #b42318;
      --ok: #067647;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: #fff;
      display: grid;
      grid-template-columns: 300px minmax(360px, 1fr) 300px;
      min-height: 100vh;
      overflow: hidden;
    }
    .left-panel, .right-panel {
      min-height: 0;
      background: var(--panel);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow: auto;
    }
    .left-panel { border-right: 1px solid var(--line); }
    .right-panel { border-left: 1px solid var(--line); }
    .stage {
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      background: #fff;
    }
    h1, h2 {
      letter-spacing: 0;
      margin: 0;
    }
    h1 { font-size: 18px; }
    h2 { font-size: 14px; }
    .subtle {
      font-size: 12px;
      color: var(--muted);
      margin-top: 4px;
    }
    label {
      font-size: 12px;
      color: var(--muted);
      display: block;
      margin-bottom: 4px;
    }
    input, textarea, button { font: inherit; }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      background: #fff;
      color: var(--ink);
    }
    textarea {
      min-height: 220px;
      resize: vertical;
      line-height: 1.45;
    }
    button {
      border: 1px solid var(--accent);
      background: var(--accent);
      color: #fff;
      border-radius: 6px;
      padding: 9px 11px;
      cursor: pointer;
      white-space: nowrap;
    }
    button.secondary {
      background: #fff;
      color: var(--accent-ink);
    }
    button:disabled {
      opacity: .55;
      cursor: not-allowed;
    }
    .button-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 8px;
    }
    .toolbar {
      border-bottom: 1px solid var(--line);
      padding: 10px 14px;
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      background: #fff;
    }
    .zoom-group {
      display: flex;
      gap: 8px;
    }
    .zoom-group button { min-width: 42px; }
    .status {
      margin-left: auto;
      font-size: 13px;
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .viewport {
      min-height: 0;
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
      padding: 28px;
      overscroll-behavior: contain;
    }
    .canvas-shell {
      width: 100%;
      height: 100%;
      min-width: 260px;
      min-height: 260px;
      display: grid;
      place-items: center;
    }
    img {
      max-width: none;
      max-height: none;
      border: 1px solid var(--line);
      background: #fff;
      box-shadow: 0 12px 32px rgba(20, 30, 45, .14);
    }
    pre {
      margin: 0;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      min-height: 120px;
      max-height: 260px;
      overflow: auto;
      font-size: 12px;
      line-height: 1.35;
      white-space: pre-wrap;
    }
    #codeLog { max-height: 360px; }
    .meta {
      background: var(--panel-strong);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.45;
    }
    .ok { color: var(--ok); }
    .bad { color: var(--bad); }
    @media (max-width: 760px) {
      body {
        grid-template-columns: 1fr;
        grid-template-rows: auto minmax(520px, 1fr) auto;
        overflow: auto;
      }
      .left-panel, .right-panel {
        border: 0;
        border-bottom: 1px solid var(--line);
        max-height: none;
      }
      .right-panel { border-top: 1px solid var(--line); }
    }
  </style>
</head>
<body>
  <aside class="left-panel">
    <div>
      <h1>Vibe Layout Viewer</h1>
      <div class="subtle">Prompt-driven GDS generation</div>
    </div>
    <div>
      <label for="token">Bearer token</label>
      <input id="token" type="password" autocomplete="off" placeholder="VIBE_LAYOUT_TOKEN">
    </div>
    <div>
      <label for="prompt">Prompt</label>
      <textarea id="prompt">[Vibe_Layout] design a Standard 6-terminal Hall Bar for Quantum Hall Effect measurement. Use a 50um main channel width, 10um voltage leads, 200um x 200um bonding pads, and place the full device on layer (1, 0).</textarea>
    </div>
    <button id="generate">Generate Layout</button>
    <div class="meta">Start layout-generation prompts with [Vibe_Layout]. Generated GDS and preview files are stored under build/jobs.</div>
  </aside>

  <main class="stage">
    <div class="toolbar">
      <h2>Layout Preview</h2>
      <div class="zoom-group">
        <button class="secondary" id="zoomOut">-</button>
        <button class="secondary" id="zoomReset">100%</button>
        <button class="secondary" id="zoomIn">+</button>
      </div>
      <span class="status" id="statusText">Ready</span>
    </div>
    <div class="viewport">
      <div class="canvas-shell">
        <img id="preview" alt="Generated layout preview" hidden>
      </div>
    </div>
  </main>

  <aside class="right-panel">
    <div>
      <h2>Artifacts</h2>
      <div class="subtle">Download generated files</div>
    </div>
    <div class="button-grid">
      <button id="openKLayout" class="secondary" disabled>Open KLayout</button>
      <button id="downloadGds" class="secondary" disabled>Download GDS</button>
      <button id="downloadPng" class="secondary" disabled>Download PNG</button>
    </div>
    <div>
      <label>Job Summary</label>
      <pre id="jobLog">No job yet.</pre>
    </div>
    <div>
      <label>Generated Code</label>
      <pre id="codeLog">No code yet.</pre>
    </div>
  </aside>
  <script>
    const tokenInput = document.getElementById("token");
    const promptInput = document.getElementById("prompt");
    const generateButton = document.getElementById("generate");
    const statusText = document.getElementById("statusText");
    const jobLog = document.getElementById("jobLog");
    const codeLog = document.getElementById("codeLog");
    const preview = document.getElementById("preview");
    const viewport = document.querySelector(".viewport");
    const openKLayout = document.getElementById("openKLayout");
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

    function renderCode(job) {
      codeLog.textContent = job.python_code || "No code generated.";
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
      renderCode(job);
      if (job.status === "completed") {
        const previewBlob = await fetchArtifactBlob(job, "preview.png");
        if (currentPreviewBlobUrl) {
          URL.revokeObjectURL(currentPreviewBlobUrl);
        }
        currentPreviewBlobUrl = URL.createObjectURL(previewBlob);
        preview.src = currentPreviewBlobUrl;
        preview.hidden = false;
        openKLayout.disabled = false;
        downloadPng.disabled = false;
        downloadGds.disabled = false;
        setStatus(`Completed ${job.job_id}`);
      } else {
        setStatus(`Job ${job.status}`, true);
      }
    }

    async function loadJob(jobId) {
      setStatus(`Loading ${jobId}...`);
      const response = await fetch(`/api/layouts/${jobId}`, { headers: authHeaders() });
      if (!response.ok) {
        throw new Error(`${response.status} ${await response.text()}`);
      }
      await renderJob(await response.json());
    }

    async function generate() {
      if (!/^\s*(\[Vibe_Layout\]|Vibe_Layout)(?:\s|[:,，-]|$)/i.test(promptInput.value)) {
        jobLog.textContent = "Prompt must begin with [Vibe_Layout].";
        codeLog.textContent = "No code generated.";
        setStatus("Missing [Vibe_Layout] command", true);
        return;
      }
      generateButton.disabled = true;
      openKLayout.disabled = true;
      downloadGds.disabled = true;
      downloadPng.disabled = true;
      preview.hidden = true;
      setStatus("Generating...");
      jobLog.textContent = "Submitting job...";
      codeLog.textContent = "Waiting for generated artifact metadata...";
      try {
        const response = await fetch("/api/layouts", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders() },
          body: JSON.stringify({ prompt: promptInput.value, open_gui: false, open_viewer: false }),
        });
        if (!response.ok) {
          throw new Error(`${response.status} ${await response.text()}`);
        }
        await renderJob(await response.json());
      } catch (error) {
        jobLog.textContent = String(error);
        codeLog.textContent = "No code generated.";
        setStatus("Failed", true);
      } finally {
        generateButton.disabled = false;
      }
    }

    function applyZoom() {
      preview.style.width = `${Math.round(zoom * 100)}%`;
      document.getElementById("zoomReset").textContent = `${Math.round(zoom * 100)}%`;
    }

    async function downloadArtifact(artifact, filename) {
      if (!currentJob) return;
      try {
        setStatus(`Preparing ${filename}...`);
        const blob = await fetchArtifactBlob(currentJob, artifact);
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setStatus(`Download started: ${filename}`);
      } catch (error) {
        setStatus(`Download failed: ${error}`, true);
      }
    }

    async function openCurrentInKLayout() {
      if (!currentJob) return;
      try {
        setStatus("Opening KLayout...");
        const response = await fetch(`/api/layouts/${currentJob.job_id}/open-klayout`, {
          method: "POST",
          headers: authHeaders(),
        });
        if (!response.ok) {
          throw new Error(`${response.status} ${await response.text()}`);
        }
        const result = await response.json();
        setStatus(`Opened in KLayout: ${result.method}`);
      } catch (error) {
        setStatus(`KLayout open failed: ${error}`, true);
      }
    }

    document.getElementById("zoomIn").addEventListener("click", () => { zoom = Math.min(6, zoom * 1.25); applyZoom(); });
    document.getElementById("zoomOut").addEventListener("click", () => { zoom = Math.max(.2, zoom / 1.25); applyZoom(); });
    document.getElementById("zoomReset").addEventListener("click", () => { zoom = 1; applyZoom(); });
    viewport.addEventListener("wheel", (event) => {
      if (!event.ctrlKey || preview.hidden) return;
      event.preventDefault();
      zoom = event.deltaY < 0 ? Math.min(6, zoom * 1.12) : Math.max(.2, zoom / 1.12);
      applyZoom();
    }, { passive: false });
    generateButton.addEventListener("click", generate);
    openKLayout.addEventListener("click", openCurrentInKLayout);
    downloadGds.addEventListener("click", () => downloadArtifact("layout.gds", "layout.gds"));
    downloadPng.addEventListener("click", () => downloadArtifact("preview.png", "preview.png"));
    applyZoom();
    const startupParams = new URLSearchParams(window.location.hash.slice(1));
    if (startupParams.has("token")) {
      tokenInput.value = startupParams.get("token");
    }
    if (startupParams.has("job_id")) {
      loadJob(startupParams.get("job_id")).catch((error) => {
        jobLog.textContent = String(error);
        setStatus("Failed to load linked job", true);
      });
    }
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
    viewer_base_url = f"http://{args.host}:{args.port}"
    uvicorn.run(
        create_app(
            token=token,
            jobs_dir=args.jobs_dir,
            auto_open_viewer=True,
            viewer_base_url=viewer_base_url,
        ),
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
