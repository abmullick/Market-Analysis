from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parent.parent
hero = root / "static" / "images" / "hero-market-analysis.png"
out_preview = root / "static" / "images" / "whatsapp-preview.jpg"
out_favicon = root / "static" / "favicon.ico"

img = Image.open(hero).convert("RGBA")

# 1200x630 social preview, matching the image-first style of the Financials app.
canvas = Image.new("RGB", (1200, 630), "white")
thumb = img.copy()
thumb.thumbnail((1000, 560), Image.Resampling.LANCZOS)
x = (1200 - thumb.width) // 2
y = (630 - thumb.height) // 2
canvas.paste(thumb, (x, y), thumb)
canvas.save(out_preview, "JPEG", quality=82, optimize=True, progressive=True)

# Use the same Market Analysis artwork for the browser favicon, replacing the old magnifying-glass icon.
icon = img.copy()
icon.thumbnail((256, 256), Image.Resampling.LANCZOS)
icon_canvas = Image.new("RGBA", (256, 256), "white")
x = (256 - icon.width) // 2
y = (256 - icon.height) // 2
icon_canvas.paste(icon, (x, y), icon)
icon_canvas.save(out_favicon, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

print(f"Created {out_preview} ({out_preview.stat().st_size} bytes)")
print(f"Created {out_favicon} ({out_favicon.stat().st_size} bytes)")
