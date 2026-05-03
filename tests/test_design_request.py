from klayout_harness import CADHarness, RecordingBackend, build_electrode_layout, parse_electrode_request
from klayout_harness.design_request import default_context_for_request


PROMPT = (
    "Vibe_Layout, $1mm \\times 1mm$ 크기의 메인 셀 'CHIP_ROOT'를 생성해줘. "
    "그 안에 'ELECTRODE_UNIT'이라는 서브 셀을 만들고, 폭 $50\\mu m$, "
    "길이 $800\\mu m$의 박스를 중앙에 배치해. 단위는 반드시 $\\mu m$ 기준이어야 하며, "
    "Microwriter에서 인식할 수 있도록 레이어는 (1, 0)으로 설정해줘."
)


def test_parse_electrode_request() -> None:
    request = parse_electrode_request(PROMPT)

    assert request.root_cell == "CHIP_ROOT"
    assert request.root_width_um == 1000
    assert request.root_height_um == 1000
    assert request.unit_cell == "ELECTRODE_UNIT"
    assert request.electrode_width_um == 50
    assert request.electrode_length_um == 800
    assert request.layer == 1
    assert request.datatype == 0


def test_build_electrode_layout_uses_subcell_instance_and_microwriter_layer() -> None:
    request = parse_electrode_request(PROMPT)
    context = default_context_for_request()
    backend = RecordingBackend()
    cad = CADHarness(context, backend=backend)

    build_electrode_layout(request, cad)

    assert backend.cells == {"CHIP_ROOT", "ELECTRODE_UNIT"}
    assert len(backend.instances) == 1
    assert backend.instances[0].parent_cell == "CHIP_ROOT"
    assert backend.instances[0].child_cell == "ELECTRODE_UNIT"
    assert backend.instances[0].x == 0
    assert backend.instances[0].y == 0

    electrode = backend.boxes[-1]
    assert electrode.cell == "ELECTRODE_UNIT"
    assert electrode.layer.layer == 1
    assert electrode.layer.datatype == 0
    assert (electrode.x1, electrode.y1, electrode.x2, electrode.y2) == (-25000, -400000, 25000, 400000)

    frame_boxes = [box for box in backend.boxes if box.cell == "CHIP_ROOT"]
    assert len(frame_boxes) == 4
