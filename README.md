# Vibe Layout

Harness-based scaffold for building an intelligent KLayout design agent.

The project keeps the agent focused on design intent while harness layers own
context, CAD operations, validation, and iterative correction.

## Architecture

- Dynamic Context Harness: loads technology context, layers, DBU, parameters,
  and basic DRC rules from external config.
- CAD Operation Harness: exposes high-level layout operations and hides direct
  KLayout API calls from agent logic.
- Feedback Harness: validates generated layouts for basic geometry and process
  constraints.
- Self-Correction Circuit: reruns design generation with validation findings
  until the layout passes or the iteration limit is reached.

## Quick Start

```powershell
python -m pip install -e .[dev,gds]
python examples/simple_cell.py
python -m pytest
```

KLayout Python bindings are loaded lazily. Unit tests use an in-memory backend,
so they can run before KLayout is installed. Real GDS generation requires the
`gds` extra or another installation that provides `klayout.db`.

## Generate From A Request

```powershell
$prompt = @'
Vibe_Layout, $1mm \times 1mm$ 크기의 메인 셀 'CHIP_ROOT'를 생성해줘. 그 안에 'ELECTRODE_UNIT'이라는 서브 셀을 만들고, 폭 $50\mu m$, 길이 $800\mu m$의 박스를 중앙에 배치해. 단위는 반드시 $\mu m$ 기준이어야 하며, Microwriter에서 인식할 수 있도록 레이어는 (1, 0)으로 설정해줘.
'@
vibe-layout $prompt --open
```

This constrained request creates a `CHIP_ROOT` cell, an `ELECTRODE_UNIT`
subcell, a centered `50 um x 800 um` electrode on layer `(1, 0)`, and a
`1 mm x 1 mm` root-cell frame.

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

## Real GDS Output

Install KLayout Python bindings so `klayout.db` or `pya` is importable, then use
`CADHarness.from_context(context)` without injecting a test backend.
