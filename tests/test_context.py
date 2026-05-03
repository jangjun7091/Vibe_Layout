from klayout_harness import DesignContext


def test_context_converts_um_to_dbu() -> None:
    context = DesignContext.from_mapping(
        {
            "dbu_um": 0.001,
            "layers": {"M1": {"layer": 1, "datatype": 0}},
            "parameters": {"width_um": 10.0},
            "rules": {"min_width_um": 0.2},
        }
    )

    assert context.dbu(1.5) == 1500
    assert context.um(1500) == 1.5
    assert context.layer("M1").layer == 1
    assert context.parameter("width_um") == 10.0
    assert context.rule("min_width_um") == 0.2
