from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
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
