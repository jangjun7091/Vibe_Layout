# Vibe Layout

Harness-based scaffold for building an intelligent KLayout design agent.

The project bridges high-level intent with precision GDS output by forcing each
request through three executable harnesses before a layout is accepted.

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

## Generate From A Request

Use a PowerShell here-string so `$1mm` and `$50\mu m` are not interpreted as
variables:

```powershell
$prompt = @'
Vibe_Layout, $1mm \times 1mm$ root cell 'CHIP_ROOT'. Create sub cell 'ELECTRODE_UNIT' with width $50\mu m$ and length $800\mu m$ on Microwriter layer (1, 0).
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
