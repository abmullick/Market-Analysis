from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parent.parent
hero = root / "static" / "images" / "hero-market-analysis.png"
out_preview = root / "static" / "images" / "whatsapp-preview.jpg"

img = Image.open(hero).convert("RGBA")

# 1200x630 social preview, matching the image-first style of the Financials app.
canvas = Image.new("RGB", (1200, 630), "white")
thumb = img.copy()
thumb.thumbnail((1000, 560), Image.Resampling.LANCZOS)
x = (1200 - thumb.width) // 2
y = (630 - thumb.height) // 2
canvas.paste(thumb, (x, y), thumb)
canvas.save(out_preview, "JPEG", quality=82, optimize=True, progressive=True)

print(f"Created {out_preview} ({out_preview.stat().st_size} bytes)")
