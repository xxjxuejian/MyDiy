"""Create a 4096 x 4096 tile test image, or crop a supplied photo."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SIZE = 4096
output = Path("input.png")
if output.exists():
    raise SystemExit("input.png already exists. Rename it before running again.")

if len(sys.argv) > 2:
    raise SystemExit('Usage: python prepare_image.py ["original.jpg"]')

if len(sys.argv) == 2:
    with Image.open(sys.argv[1]) as source:
        image = ImageOps.fit(
            ImageOps.exif_transpose(source).convert("RGB"),
            (SIZE, SIZE),
            method=Image.Resampling.LANCZOS,
        )
else:
    image = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    font = ImageFont.truetype(str(font_path), 32) if font_path.exists() else ImageFont.load_default(size=32)
    large_font = ImageFont.truetype(str(font_path), 88) if font_path.exists() else ImageFont.load_default(size=88)

    for row in range(16):
        for col in range(16):
            x, y = col * 256, row * 256
            color = (70 + col * 8, 75 + row * 8, 155)
            draw.rectangle((x, y, x + 255, y + 255), fill=color, outline="white", width=3)
            draw.text((x + 16, y + 104), f"x={col}, y={row}", font=font, fill="white")

    corners = [
        (0, 0, "TOP LEFT", "#b83232"),
        (3072, 0, "TOP RIGHT", "#256f40"),
        (0, 3840, "BOTTOM LEFT", "#275cb4"),
        (3072, 3840, "BOTTOM RIGHT", "#873ba6"),
    ]
    for x, y, label, color in corners:
        draw.rectangle((x, y, x + 1023, y + 92), fill=color)
        draw.text((x + 12, y + 4), label, font=large_font, fill="white")

image.save(output)
print(f"Saved {output.resolve()} ({image.width} x {image.height})")
