from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

from verify import PhotoResult


def palette_colors(results: list[PhotoResult]) -> list[tuple[int, int, int]]:
    return [result.color for result in results if result.accepted and result.color][:5]


def palette_png(results: list[PhotoResult], color_name: str = "") -> bytes:
    """Five swatches on a white plate with thin rules, sized for sharing."""
    swatches = palette_colors(results)
    width, height, margin, band = 1500, 520, 60, 300
    image = Image.new("RGB", (width, height), (247, 248, 249))
    draw = ImageDraw.Draw(image)
    ink, muted = (17, 17, 17), (130, 134, 140)
    draw.line((margin, margin, width - margin, margin), fill=ink, width=2)
    draw.text((margin, margin + 16), "COLOR LOOP", fill=ink)
    draw.text((width - margin - 220, margin + 16), f"TARGET / {color_name.upper()}", fill=muted)
    top = margin + 70
    slot = (width - 2 * margin) / 5
    for index in range(5):
        left = int(margin + index * slot)
        right = int(margin + (index + 1) * slot) - 12
        box = (left, top, right, top + band)
        if index < len(swatches):
            color = swatches[index]
            draw.rectangle(box, fill=color)
            draw.text((left, top + band + 14), f"{index + 1:02d}", fill=ink)
            draw.text((left + 40, top + band + 14), "#{:02X}{:02X}{:02X}".format(*color), fill=muted)
        else:
            draw.rectangle(box, outline=(200, 203, 207), width=1)
            draw.line((left, top + band, right, top), fill=(200, 203, 207), width=1)
            draw.text((left, top + band + 14), f"{index + 1:02d}", fill=muted)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
