from pathlib import Path

from klayout_harness import CADHarness, DesignContext, FeedbackHarness, RecordingBackend


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    context = DesignContext.from_file(ROOT / "configs" / "example_tech.yaml")
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    cad.create_cell("TOP")
    cad.add_box_um("TOP", "M1", 0, 0, context.parameter("cell_width_um"), context.parameter("cell_height_um"))
    cad.add_text_um("TOP", "TEXT", "TOP", 1, 1)
    cad.write_gds(ROOT / "build" / "simple_cell.gds")

    report = FeedbackHarness(context).validate_recording(
        backend,
        expected_cells={"TOP"},
        expected_layers={"M1"},
    )
    print(f"validation_passed={report.passed}")


if __name__ == "__main__":
    main()
