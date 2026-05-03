from __future__ import annotations

from pathlib import Path


def render_gds_preview(
    gds_path: str | Path,
    png_path: str | Path,
    root_cell_name: str,
    layer: int | None = None,
    datatype: int | None = None,
    scale_px_per_um: float = 1.1,
    pad_um: float = 40.0,
) -> Path:
    from PIL import Image, ImageDraw
    import klayout.db as kdb

    gds = Path(gds_path)
    output = Path(png_path)
    layout = kdb.Layout()
    layout.read(str(gds))
    root = layout.cell(root_cell_name)
    if root is None:
        raise ValueError(f"Root cell '{root_cell_name}' not found in {gds}")

    bbox = root.bbox()
    width_um = bbox.width() * layout.dbu
    height_um = bbox.height() * layout.dbu
    image_width = max(1, int((width_um + 2 * pad_um) * scale_px_per_um))
    image_height = max(1, int((height_um + 2 * pad_um) * scale_px_per_um))
    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    min_x_um = bbox.left * layout.dbu - pad_um
    max_y_um = bbox.top * layout.dbu + pad_um

    def to_px(x_dbu: int, y_dbu: int) -> tuple[int, int]:
        x_um = x_dbu * layout.dbu
        y_um = y_dbu * layout.dbu
        return int((x_um - min_x_um) * scale_px_per_um), int((max_y_um - y_um) * scale_px_per_um)

    x1, y1 = to_px(bbox.left, bbox.bottom)
    x2, y2 = to_px(bbox.right, bbox.top)
    draw.rectangle([x1, y2, x2, y1], outline=(30, 30, 30), width=2)

    colors = [(20, 120, 210), (30, 30, 30), (45, 160, 90), (180, 80, 30)]
    layer_indexes = [layout.layer(layer, datatype)] if layer is not None and datatype is not None else list(layout.layer_indexes())
    for layer_offset, layer_index in enumerate(layer_indexes):
        layer_info = layout.get_info(layer_index)
        layer_color = colors[layer_offset % len(colors)]
        if layer_info.layer == 2:
            layer_color = (45, 160, 90)
        for cell_index, cell in enumerate(layout.each_cell()):
            color = layer_color if cell.name != root_cell_name else (30, 30, 30)
            if cell.name != root_cell_name and cell_index:
                color = layer_color
            for shape in cell.shapes(layer_index).each():
                if not shape.is_box():
                    continue
                box = shape.box
                bx1, by1 = to_px(box.left, box.bottom)
                bx2, by2 = to_px(box.right, box.top)
                draw.rectangle([bx1, by2, bx2, by1], fill=color, outline=color)

    if layer is not None and datatype is not None:
        # Keep backward-compatible single-layer previews visually identical for existing designs.
        pass

    bar_um = 100
    bar_x = 60
    bar_y = image_height - 45
    bar_len = int(bar_um * scale_px_per_um)
    draw.line([bar_x, bar_y, bar_x + bar_len, bar_y], fill=(0, 0, 0), width=3)
    draw.text((bar_x, bar_y + 8), "100 um", fill=(0, 0, 0))

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return output
