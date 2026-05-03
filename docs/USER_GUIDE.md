# Vibe_Layout User Guide

This guide explains how to use Vibe_Layout as an open-source layout generation
tool from a terminal, Codex, or Claude Code.

## 1. Install

Use Python 3.11 or newer.

```powershell
git clone https://github.com/jangjun7091/Vibe_Layout.git
cd Vibe_Layout
python -m pip install -e .[dev,gds,server]
python -m pytest
```

The `gds` extra installs KLayout Python bindings for real GDS generation. The
test suite also includes in-memory backend coverage, so most logic can be
developed without opening the KLayout GUI.

## 2. Start The Viewer Server

```powershell
$env:VIBE_LAYOUT_TOKEN = "local-dev-token"
vibe-layout-server --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765/viewer
```

The Viewer provides prompt input, layout preview, generated KLayout code, job
summary, download buttons, and an Open KLayout button when KLayout is available.

## 3. Generate A Layout

Every design-generation prompt should begin with `[Vibe_Layout]`.

Example:

```text
[Vibe_Layout] Design a bio sensor Micro-channel pattern. The fluid flow should
be smooth and the reaction area should be large. Use Microwriter layer (1, 0).
```

Vibe_Layout will:

1. Resolve the prompt into typed physical parameters.
2. Generate parametric KLayout geometry.
3. Write GDS under `build/jobs/{job_id}/`.
4. Render a PNG preview.
5. Validate DBU precision, minimum resolution, layer usage, hierarchy, and GDS
   readback.

## 4. Use Inside Codex

Open this repository in Codex and start the local server. When asking Codex to
generate a layout, include `[Vibe_Layout]` at the start of the request.

Codex should open the returned `agent_action.url` or `viewer_url` in the Codex
in-app browser. The primary result should be Vibe Layout Viewer, not a raw PNG
preview.

## 5. Use Inside Claude Code

Open this repository in Claude Code and start the local server. Claude Code
should follow `CLAUDE.md`: submit the prompt to the local API, read
`agent_action.url`, and open that URL in the Claude Code browser preview.

If the browser lands on `/viewer#job_id=` without a job id, call
`GET /api/layouts/latest` and open the returned `agent_action.url`.

## 6. API Contract

Create a layout:

```http
POST /api/layouts
Authorization: Bearer <token>
Content-Type: application/json

{ "prompt": "[Vibe_Layout] ...", "open_gui": false }
```

Important response fields:

- `job_id`: generated layout job id.
- `viewer_url`: canonical Viewer URL for human review.
- `agent_action.url`: URL agents should open in their internal browser.
- `gds_path`: generated GDS path.
- `preview_path`: generated PNG preview path.
- `validation_passed`: whether the layout passed validation.
- `findings`: validation issues if any.

## 7. Development Checklist

Before submitting changes:

```powershell
python -m pytest
git status --short
```

Do not commit generated build artifacts under `build/`. Commit only source,
tests, documentation, and intentionally curated images under `docs/images/`.

## Roadmap

- More parametric layout families.
- Process-specific DRC profiles.
- Direct KLayout macro/plugin bridge for live GUI synchronization.
- Richer Viewer controls for editing parameters after semantic parsing.
- CI that runs tests and regenerates representative preview images.
