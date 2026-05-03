# Vibe_Layout

Prompt-to-GDS layout generation for KLayout, Codex, and Claude Code.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![KLayout](https://img.shields.io/badge/KLayout-GDSII-2f6f4e)](https://www.klayout.de/)
[![FastAPI](https://img.shields.io/badge/FastAPI-realtime%20viewer-009688)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Vibe_Layout is an open-source, harness-based KLayout design agent that turns
high-level layout intent into verified GDS output.

The project bridges high-level intent with precision GDS output by forcing each
request through three executable harnesses before a layout is accepted.

- Use it from the command line for reproducible GDS generation.
- Use it as a local realtime server with Vibe Layout Viewer.
- Use it inside Codex or Claude Code by asking an agent to run `[Vibe_Layout]`
  prompts and open the returned Viewer URL in the agent's browser surface.

The canonical review surface is Vibe Layout Viewer. PNG previews and raw GDS
files are downloadable artifacts, but users should inspect generated layouts in
the Viewer first and then optionally open the same GDS in KLayout.

![Vibe Layout Viewer showing a generated bio sensor micro-channel](docs/images/micro-channel%20viewer.png)

## Why Vibe_Layout?

- Prompt-to-GDS: convert high-level device intent into layout geometry.
- Verification first: reject invalid layouts instead of silently writing GDS.
- Agent ready: designed for Codex and Claude Code workflows.
- Local-first: runs on localhost with bearer-token protected HTTP and WebSocket
  APIs.
- KLayout-native: generates reproducible `klayout.db` Python code and GDS.

## Result Gallery

Representative generated previews are committed under `docs/images/` so the
GitHub project page shows the current layout capabilities at a glance.

| Electrode unit | Bio sensor micro-channel |
| --- | --- |
| ![Centered electrode unit](docs/images/electrode-unit.png) | ![Bio sensor micro-channel](docs/images/micro-channel.png) |
| `[Vibe_Layout] $1mm \times 1mm$ root cell 'CHIP_ROOT'. Create sub cell 'ELECTRODE_UNIT' with width $50\mu m$ and length $800\mu m$ on Microwriter layer (1, 0).` | `[Vibe_Layout] Design a bio sensor Micro-channel pattern. The fluid flow should be smooth and the reaction area should be large. Use Microwriter layer (1, 0).` |

| 6-terminal Hall bar | Nano-gap array |
| --- | --- |
| ![Standard 6-terminal Hall bar](docs/images/hall-bar-6t.png) | ![Tunneling nano-gap array](docs/images/nanogap-array.png) |
| `[Vibe_Layout] Design a Standard 6-terminal Hall Bar for Quantum Hall Effect measurement. Use a 50um main channel width, 10um voltage leads, 200um x 200um bonding pads, and place the full device on layer (1, 0).` | `[Vibe_Layout] Design a tunneling effect Nano-gap array. Sweep the gap between two electrodes from 0.6um to 2.0um in 0.2um steps for 8 devices arranged horizontally. Keep 100um spacing between devices and add identifier box patterns on layer (2, 0).` |

| Vibe Layout Viewer workflow | KLayout verification view |
| --- | --- |
| ![Bio sensor micro-channel in Vibe Layout Viewer](docs/images/micro-channel%20viewer.png) | ![Bio sensor micro-channel opened in KLayout](docs/images/micro-channel%20KLayout.png) |
| `[Vibe_Layout] Bio sensor micro-channel request shown inside the local Viewer with prompt, layout preview, artifacts, job summary, and generated KLayout code.` | `The same generated BIO_SENSOR_ROOT.gds opened in KLayout for independent layout inspection on layer (1, 0).` |

## What You Can Build Today

The current scaffold supports these layout intents:

- Centered electrode unit inside a `1 mm x 1 mm` root frame.
- Bio sensor serpentine micro-channel.
- Standard 6-terminal Hall bar.
- Tunneling nano-gap array with gap sweep and marker layer.
- SRR feedline inductive coupling device.

Each supported intent goes through semantic parsing, parametric KLayout
actuation, preview rendering, and validation before the job is accepted.

## Architecture

- Semantic Harness: converts user intent into typed physical parameters in
  micrometers, resolves Microwriter defaults, and enforces fabrication-aware
  semantic constraints.
- Tool-Actuation Harness: generates layouts through parametric `klayout.db`
  operations hidden behind `CADHarness`.
- Verification Harness: validates DBU mapping, minimum resolution, positive
  closed rectangular geometry, layer usage, hierarchy, and real GDS readback.

The Microwriter minimum resolution rule is a hard `0.6 um` DRC limit.

## Quick Start

```powershell
python -m pip install -e .[dev,gds]
python -m pytest
```

KLayout Python bindings are loaded lazily. Unit tests use an in-memory backend,
so most tests can run before KLayout is installed. Real GDS generation requires
the `gds` extra or another installation that provides `klayout.db`.

For a fuller walkthrough, see [docs/USER_GUIDE.md](docs/USER_GUIDE.md).
To add a new supported device family, see
[docs/ADDING_LAYOUT_INTENTS.md](docs/ADDING_LAYOUT_INTENTS.md).

## Generate From A Request

Use a PowerShell here-string so `$1mm` and `$50\mu m` are not interpreted as
variables:

```powershell
$prompt = @'
[Vibe_Layout] $1mm \times 1mm$ root cell 'CHIP_ROOT'. Create sub cell 'ELECTRODE_UNIT' with width $50\mu m$ and length $800\mu m$ on Microwriter layer (1, 0).
'@
vibe-layout $prompt --open
```

The CLI prints three required sections:

- Engineering Analysis
- Python Code
- Design Validation

The constrained electrode request creates a `CHIP_ROOT` cell, an
`ELECTRODE_UNIT` subcell, a centered `50 um x 800 um` electrode on layer
`(1, 0)`, and a `1 mm x 1 mm` root-cell frame.

## KLayout GUI

To open the generated file in the KLayout GUI on Windows, install KLayout GUI
and use one of these options:

```powershell
$env:KLAYOUT_EXE = "C:\Path\To\klayout.exe"
vibe-layout $prompt --open
```

or:

```powershell
vibe-layout $prompt --open --klayout-exe "C:\Path\To\klayout.exe"
```

If no executable is found, the CLI falls back to Windows `.gds` file
association.

## Realtime Server

Install server dependencies and start the localhost API:

```powershell
python -m pip install -e .[dev,gds,server]
$env:VIBE_LAYOUT_TOKEN = "local-dev-token"
vibe-layout-server --host 127.0.0.1 --port 8765
```

Create a layout job:

```powershell
$headers = @{ Authorization = "Bearer local-dev-token" }
$body = @{ prompt = $prompt; open_gui = $false } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/layouts" -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

Useful endpoints:

- `POST /api/layouts`
- `GET /api/layouts/{job_id}`
- `GET /api/layouts/latest`
- `GET /api/layouts/{job_id}/preview.png`
- `GET /api/layouts/{job_id}/layout.gds`
- `WS /ws/jobs/{job_id}`

Successful `POST /api/layouts` responses include `viewer_url` and
`agent_action`. Agents should open `agent_action.url` inside their active
browser surface, such as the Codex in-app browser or Claude Code browser
preview. The Viewer URL is the canonical review surface; generated PNG, GDS,
and standalone HTML artifacts are secondary downloads.
If `/viewer#job_id=` is opened without a job id, the Viewer attempts to load the
latest layout job through `GET /api/layouts/latest`.

The server stores generated artifacts under `build/jobs/{job_id}/` and requires
`Authorization: Bearer <token>` for API and WebSocket access.

## Use With Codex Or Claude Code

Vibe_Layout is designed to work inside agent coding environments. Open the
repository in Codex or Claude Code, start the local server, and ask the agent
with a prompt that begins with `[Vibe_Layout]`.

Agent rule:

1. Submit the prompt to `POST /api/layouts`.
2. Read the returned `agent_action.url` or `viewer_url`.
3. Open that URL in the active agent browser surface:
   - Codex: Codex in-app browser.
   - Claude Code: Claude Code browser preview.
4. Do not open `preview.png` as the primary result when a Viewer URL exists.

The repository includes [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) so
other agents can discover this rule when they work in the project.

## Project Status And Next Work

Vibe_Layout is an early but executable scaffold. The core workflow is working:
prompt to spec, spec to GDS, GDS to preview, validation, Viewer, and artifact
download.

Recommended next work:

- Add more MEMS, sensor, superconducting, RF, and microfluidic layout families.
- Add a richer parameter editor in Vibe Layout Viewer.
- Add direct KLayout macro/plugin bridge support for live GUI synchronization.
- Add design-rule profiles for different fabrication processes.
- Extend GitHub Actions CI with generated example artifact checks.
- Expand contribution examples and issue templates as new layout families land.

## Contributing

Contributions are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md), and
open focused pull requests for one layout family, harness improvement, or Viewer
feature at a time.

## License

Vibe_Layout is released under the [MIT License](LICENSE).
