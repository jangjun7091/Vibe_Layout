# Adding Layout Intents

This guide explains how to add a new supported device family to Vibe_Layout.

## Goal

A layout intent is a complete prompt-to-GDS path for one device family, such as
a Hall bar, nano-gap array, micro-channel, or resonator.

Each intent should provide:

- A typed spec in micrometers.
- Semantic parsing from `[Vibe_Layout]` prompts.
- Parametric KLayout generation.
- Validation rules.
- Tests and at least one representative prompt.

## 1. Add A Typed Spec

Add a dataclass in `src/klayout_harness/semantic.py`.

The spec should use physical units in field names, for example:

```python
channel_width_um: float
lead_spacing_um: float
layer: int
datatype: int
```

Avoid hardcoded DBU values in the spec. DBU conversion belongs inside the CAD
harness.

## 2. Extend Semantic Parsing

Update `SemanticHarness.parse()` so it can detect the new intent and return the
new typed spec.

Parsing should:

- Require `[Vibe_Layout]` for design-generation prompts.
- Normalize dimensions into micrometers.
- Resolve layer and datatype.
- Attach fabrication rules such as `minimum_resolution_um = 0.6`.

## 3. Add Tool Actuation

Update `src/klayout_harness/actuation.py` to route the new spec into a builder.

Use `CADHarness` operations instead of writing directly to `klayout.db` in
feature code. If a reusable operation is missing, add it to
`src/klayout_harness/cad.py`.

## 4. Add Verification

Update `src/klayout_harness/feedback.py` with checks for the new geometry.

Typical checks:

- No generated feature below the process minimum resolution.
- Spacing is above process limits.
- Requested dimensions map cleanly to integer DBU.
- Expected cells, hierarchy, layers, and bounding boxes exist after GDS readback.

## 5. Add Tests

Add focused tests under `tests/`.

Recommended coverage:

- Semantic parser resolves the prompt into the expected typed spec.
- Invalid dimensions fail before GDS generation.
- Valid dimensions generate GDS and preview artifacts.
- GDS readback confirms cell names, layers, hierarchy, and bounding boxes.

## 6. Add Documentation

Update `README.md` or `docs/USER_GUIDE.md` when the new intent should be
visible to users. If the design is visually useful, add a curated screenshot to
`docs/images/`.

## Pull Request Checklist

- `python -m pytest` passes.
- Generated files under `build/` are not staged.
- New behavior is reachable through `[Vibe_Layout]` prompts.
- The Viewer remains the primary review surface.
