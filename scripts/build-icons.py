# /// script
# requires-python = ">=3.9"
# dependencies = ["pillow"]
# ///
"""Rebuild every page's favicon.png and the icon-*.png home-screen icons from assets/noto-emoji.woff2.

Run after changing a page's emoji (and after build-emoji-font.py):  uv run scripts/build-icons.py

Chrome draws the glyphs (Pillow can't render the COLRv1 colour emoji). Set CHROME if it isn't found.
"""

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FAVICONS = {".": "🐱", "catoku": "🐱", "catwalk": "🐾", "kattenratten": "🐭", "meowsweeper": "🙀", "purrlink": "🧶"}
CREAM = (253, 246, 240, 255)
CHROME = os.environ.get("CHROME") or next(
    p for p in [
        shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ] if p and Path(p).exists()
)


def render(emoji, tmp):
    """The emoji as Chrome draws it with the pages' font, cropped to its ink."""
    font = base64.b64encode((ROOT / "assets" / "noto-emoji.woff2").read_bytes()).decode()
    page, shot = tmp / "e.html", tmp / "e.png"
    page.write_text(
        f"<!doctype html><style>@font-face{{font-family:N;src:url(data:font/woff2;base64,{font})}}"
        f"body{{margin:0}}div{{font:800px/1 N;padding:100px}}</style><div>{emoji}</div>",
        encoding="utf8",
    )
    subprocess.run(
        [CHROME, "--headless=new", f"--user-data-dir={tmp / 'profile'}", "--disable-gpu",
         "--hide-scrollbars", "--default-background-color=00000000", "--virtual-time-budget=3000",
         "--window-size=1100,1100", f"--screenshot={shot}", page.as_uri()],
        check=True, capture_output=True,
    )
    img = Image.open(shot).convert("RGBA")
    assert img.getbbox(), f"Chrome drew nothing for {emoji}"
    return img.crop(img.getbbox())


def place(glyph, size, scale, background):
    """`glyph` centred on a `size` square, its longer side `scale` of the square."""
    s = scale * size / max(glyph.size)
    g = glyph.resize((round(glyph.width * s), round(glyph.height * s)), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), background)
    out.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2))
    return out


def main():
    with tempfile.TemporaryDirectory() as tmp:
        glyphs = {e: render(e, Path(tmp)) for e in set(FAVICONS.values())}
    for d, emoji in FAVICONS.items():
        place(glyphs[emoji], 64, 0.94, (0, 0, 0, 0)).save(ROOT / d / "favicon.png", optimize=True)
    for n in (180, 192, 512):  # the 🐱 home-screen icon every page shares; 0.57: well inside the maskable safe zone
        place(glyphs["🐱"], n, 0.57, CREAM).save(ROOT / f"icon-{n}.png", optimize=True)
    print("favicons:", ", ".join(FAVICONS), "| icons: icon-180/192/512.png")


if __name__ == "__main__":
    main()
