# Contributing To Vibe_Layout

Vibe_Layout is an early open-source scaffold for prompt-driven KLayout design
automation. Contributions should keep the harness architecture explicit and
fabrication-aware.

## Development Setup

```powershell
git clone https://github.com/jangjun7091/Vibe_Layout.git
cd Vibe_Layout
python -m pip install -e .[dev,gds,server]
python -m pytest
```

## Contribution Scope

Good first contribution areas:

- Add a new parametric layout family.
- Improve semantic parsing for an existing layout family.
- Add validation rules for geometry, DBU precision, spacing, or layer usage.
- Improve Vibe Layout Viewer controls and artifact handling.
- Add examples, screenshots, and documentation.

Keep pull requests focused. A single PR should usually touch one design intent,
one harness improvement, or one Viewer feature.

## Harness Rules

Every generated design should pass through:

1. Semantic Harness: convert prompt intent into typed physical parameters.
2. Tool-Actuation Harness: generate geometry through reusable KLayout operations.
3. Verification Harness: validate process rules and generated GDS readback.

Do not bypass the harnesses by adding one-off GDS writing code in the CLI or
server.

## Testing

Before opening a PR:

```powershell
python -m pytest
git status --short
```

Tests should cover:

- Semantic parsing for representative prompts.
- Validation failure for sub-resolution or malformed geometry.
- Successful GDS and preview generation.
- Viewer/API behavior when the change touches server code.

Do not commit generated files under `build/`. Curated gallery images may be
committed under `docs/images/` when they help explain a supported workflow.

## Agent Workflow

When using Codex or Claude Code, prompts that generate layouts should begin with
`[Vibe_Layout]`. Agents should open `agent_action.url` or `viewer_url` in their
internal browser surface and should not show `preview.png` as the primary
result.
