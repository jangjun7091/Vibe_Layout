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
python -m pip install -e .[dev]
python examples/simple_cell.py
python -m pytest
```

KLayout Python bindings are loaded lazily. Unit tests use an in-memory backend,
so they can run before KLayout is installed.

## Real GDS Output

Install KLayout Python bindings so `klayout.db` or `pya` is importable, then use
`CADHarness.from_context(context)` without injecting a test backend.
