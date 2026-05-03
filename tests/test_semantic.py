import pytest

from klayout_harness import SemanticHarness


PROMPT = (
    "[Vibe_Layout] $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
    "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
    "on Microwriter layer (1, 0)."
)


def test_semantic_harness_parses_physical_parameters() -> None:
    spec = SemanticHarness().parse(PROMPT)

    assert spec.root_cell == "CHIP_ROOT"
    assert spec.root_width_um == 1000
    assert spec.root_height_um == 1000
    assert spec.unit_cell == "ELECTRODE_UNIT"
    assert spec.electrode_width_um == 50
    assert spec.electrode_length_um == 800
    assert spec.layer == 1
    assert spec.datatype == 0


def test_semantic_harness_sets_microwriter_resolution_default() -> None:
    spec = SemanticHarness().parse(PROMPT)

    assert spec.rules.process == "Microwriter"
    assert spec.rules.minimum_resolution_um == 0.6
    assert spec.rules.dbu_um == 0.001


def test_semantic_harness_rejects_subresolution_dimensions() -> None:
    spec = SemanticHarness().parse(
        "[Vibe_Layout] $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
        "Create sub cell 'ELECTRODE_UNIT' with width $0.5\\mu m$ and length $800\\mu m$ "
        "on Microwriter layer (1, 0)."
    )

    errors = SemanticHarness().validate_spec(spec)

    assert any("below Microwriter minimum resolution" in error for error in errors)


def test_semantic_harness_requires_vibe_layout_command() -> None:
    with pytest.raises(ValueError, match=r"\[Vibe_Layout\]"):
        SemanticHarness().parse(
            "$1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
            "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
            "on Microwriter layer (1, 0)."
        )


def test_semantic_harness_accepts_legacy_unbracketed_command() -> None:
    spec = SemanticHarness().parse(
        "Vibe_Layout, $1mm \\times 1mm$ root cell 'CHIP_ROOT'. "
        "Create sub cell 'ELECTRODE_UNIT' with width $50\\mu m$ and length $800\\mu m$ "
        "on Microwriter layer (1, 0)."
    )

    assert spec.root_cell == "CHIP_ROOT"
