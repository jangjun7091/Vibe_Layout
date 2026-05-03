from klayout_harness import CADHarness, DesignContext, RecordingBackend


def test_cad_harness_resolves_units_and_layers() -> None:
    context = DesignContext.from_mapping(
        {
            "dbu_um": 0.001,
            "layers": {"M1": {"layer": 1, "datatype": 0}},
            "parameters": {},
            "rules": {},
        }
    )
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.add_box_um("TOP", "M1", 0.0, 0.0, 2.0, 1.0)

    assert backend.cells == {"TOP"}
    assert len(backend.boxes) == 1
    assert backend.boxes[0].x2 == 2000
    assert backend.boxes[0].y2 == 1000
    assert backend.boxes[0].layer.name == "M1"
