# /// script
# requires-python = ">=3.9"
# dependencies = ["fonttools", "brotli", "lxml"]
# ///
"""Rebuild assets/noto-emoji.woff2: Google's Noto Color Emoji, subset to the emoji the pages use.

Run after adding an emoji anywhere:  uv run assets/build-emoji-font.py

One font, two colour tables: COLRv1 (Chrome, Firefox) + OT-SVG (Safari, which lacks COLRv1).
Both come from Google Fonts, which serves each browser whichever format it supports.
"""

import copy
import io
import re
import urllib.parse
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables.S_V_G_ import SVGDocument

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "noto-emoji.woff2"

# Not ✓ ✕ → ⇒: those stay text.
EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-⛿✅❌⭐⭕]")

USER_AGENTS = {
    "colrv1": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "otsvg": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/18.0 Safari/605.1.15"
    ),
}


def fetch(url, user_agent):
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request) as response:
        return response.read()


def fetch_fonts(text, user_agent):
    """Download the Noto Color Emoji files Google Fonts serves this browser for `text`."""
    css_url = (
        "https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&text="
        + urllib.parse.quote(text)
    )
    css = fetch(css_url, user_agent).decode()
    return [
        TTFont(io.BytesIO(fetch(url, user_agent)), lazy=False)
        for url in re.findall(r"url\((.*?)\)", css)
    ]


def subset_font(font, codepoints, **options):
    opts = subset.Options()
    opts.layout_features = []
    opts.name_IDs = ["*"]
    for key, value in options.items():
        setattr(opts, key, value)
    subsetter = subset.Subsetter(opts)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    return font


def used_codepoints():
    pages = [ROOT / "index.html", *sorted(ROOT.glob("*/index.html"))]
    found = set()
    for page in pages:
        found.update(
            ord(char) for char in EMOJI.findall(page.read_text(encoding="utf8"))
        )
    return sorted(found)


def svg_documents(codepoints, text, target):
    """One OT-SVG document per emoji, renumbered to the glyph ids of the `target` font."""
    target_cmap = target.getBestCmap()
    target_glyph_order = target.getGlyphOrder()
    svg_fonts = fetch_fonts(text, USER_AGENTS["otsvg"])
    documents = []
    for codepoint in codepoints:
        source = next(f for f in svg_fonts if codepoint in f.getBestCmap())
        # Subset per glyph so its SVG document is pruned to just that glyph.
        font = subset_font(copy.deepcopy(source), [codepoint])
        glyph_id = font.getGlyphOrder().index(font.getBestCmap()[codepoint])
        target_id = target_glyph_order.index(target_cmap[codepoint])

        [doc] = [
            d
            for d in font["SVG "].docList
            if d.startGlyphID <= glyph_id <= d.endGlyphID
        ]
        assert doc.startGlyphID == doc.endGlyphID, (
            f"shared SVG document for {codepoint:x}"
        )
        assert font["head"].unitsPerEm == target["head"].unitsPerEm, (
            "unitsPerEm differs"
        )

        data = doc.data.replace(f'id="glyph{glyph_id}"', f'id="glyph{target_id}"')
        documents.append(SVGDocument(data, target_id, target_id, False))
    return sorted(documents, key=lambda d: d.startGlyphID)


def main():
    codepoints = used_codepoints()
    text = "".join(map(chr, codepoints))

    [font] = fetch_fonts(text, USER_AGENTS["colrv1"])
    cmap = font.getBestCmap()
    for codepoint in codepoints:
        assert codepoint in cmap, f"Noto has no {codepoint:x}"

    font["SVG "] = newTable("SVG ")
    font["SVG "].docList = svg_documents(codepoints, text, font)
    subset_font(font, codepoints, layout_features=["*"])
    font.flavor = "woff2"
    font.save(OUT)
    print(len(codepoints), "emoji:", text)


if __name__ == "__main__":
    main()
