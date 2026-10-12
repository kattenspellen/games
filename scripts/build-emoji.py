# /// script
# requires-python = ">=3.9"
# dependencies = ["fonttools", "brotli", "lxml"]
# ///
"""Rebuild assets/emoji/: Google's Noto Color Emoji art, one SVG per emoji the pages use.

Run after adding an emoji anywhere:  uv run scripts/build-emoji.py

The pages swap each emoji for an <img> of its SVG, so every device draws the same art with
no font support needed. The art is the OT-SVG Google Fonts serves Safari, cut out one glyph
per file and framed on the font's line box, so it sits where the font's glyph did.
"""

import copy
import io
import re
import urllib.parse
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "emoji"

# Keep in step with EMOJI_RE in the pages' emoji images section.
# Not ✓ ✕ → ⇒ ☰ ⋮: those stay text (☰ ⋮ aren't in Noto).
EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-☯☱-⛿✅❌⭐⭕⬆]")

USER_AGENT = (  # Safari gets the OT-SVG build of Noto Color Emoji
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response:
        return response.read()


def fetch_fonts(text):
    """Download the Noto Color Emoji files Google Fonts serves Safari for `text`."""
    css_url = (
        "https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&text="
        + urllib.parse.quote(text)
    )
    css = fetch(css_url).decode()
    return [
        TTFont(io.BytesIO(fetch(url)), lazy=False)
        for url in re.findall(r"url\((.*?)\)", css)
    ]


def used_codepoints():
    pages = [ROOT / "index.html", *sorted(ROOT.glob("*/index.html"))]
    found = set()
    for page in pages:
        found.update(
            ord(char) for char in EMOJI.findall(page.read_text(encoding="utf8"))
        )
    return sorted(found)


def glyph_svg(font, codepoint):
    """The glyph's SVG document, framed as one em of a line-height:1 line around the glyph."""
    opts = subset.Options()
    opts.layout_features = []
    subsetter = subset.Subsetter(opts)
    subsetter.populate(unicodes=[codepoint])
    subsetter.subset(font)  # prunes the SVG table to just this glyph's document
    name = font.getBestCmap()[codepoint]
    glyph_id = font.getGlyphOrder().index(name)
    [doc] = [d for d in font["SVG "].docList if d.startGlyphID <= glyph_id <= d.endGlyphID]
    assert doc.startGlyphID == doc.endGlyphID, f"shared SVG document for {codepoint:x}"

    # Font units, y down from the baseline. Noto draws past the em, so the frame is the font's
    # whole ascent..descent box, square and centred on the advance; the pages' img.emo CSS sizes
    # and shifts that box to sit where the glyph did (keep the two in step).
    ascent, descent = font["hhea"].ascent, -font["hhea"].descent
    size, advance = ascent + descent, font["hmtx"][name][0]
    top, left = -ascent, (advance - size) / 2
    view = f'viewBox="{left:g} {top:g} {size} {size}"'
    return re.sub(r"<svg\b", f"<svg {view}", doc.data, count=1)


def main():
    codepoints = used_codepoints()
    text = "".join(map(chr, codepoints))
    fonts = fetch_fonts(text)
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.svg"):
        stale.unlink()
    for codepoint in codepoints:
        source = next((f for f in fonts if codepoint in f.getBestCmap()), None)
        assert source, f"Noto has no {codepoint:x}"
        svg = glyph_svg(copy.deepcopy(source), codepoint)
        (OUT / f"{codepoint:x}.svg").write_text(svg, encoding="utf8")
    print(len(codepoints), "emoji:", text)


if __name__ == "__main__":
    main()
