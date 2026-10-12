# /// script
# requires-python = ">=3.9"
# dependencies = ["playwright", "pillow"]
# ///
"""Rebuild assets/<game>-demo.gif and assets/<game>-preview.png by playing a fixed board of each game to a win.

Run after any visible UI change:  uv run scripts/build-demos.py [game …]

Playwright drives the installed Chrome (no `playwright install`); set CHROME if it isn't found. Each game's
adapter runs the game's own deductive solver with its `log` hook and replays the trace with a drawn 👆 cursor,
using the player's marks (✕ tiles, line taps, flags, strands, pieces). Before each step its reason (the
row, column, region, clue or tile that forces it) is outlined. The CDP screencast records it. The preview is the
board one move before the win. A new game needs an adapter here.
"""

import asyncio
import base64
import functools
import http.server
import io
import itertools
import json
import math
import os
import shutil
import sys
import threading
import time
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
GAMES = {"purrlink": (5, 3), "catoku": (5, 8), "kattenratten": (5, 6), "meowsweeper": (5, 2), "catwalk": (5, 216)}  # N, seed "demo|<game>|<k>"
SIZE = 700
PAUSE = 0.5  # between steps
MARK = 1.2  # a step's reason shows this long before its moves
GLIDE = 0.45  # hand travel between targets
GAP = 0.066  # frames closer than this merge (~15 fps)
CHROME = os.environ.get("CHROME") or next(
    p for p in [
        shutil.which("chrome"), shutil.which("google-chrome"), shutil.which("chromium"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ] if p and Path(p).exists()
)
# Before the page's own script: a seeded Math.random (cosmetic picks only, so reruns give the same frames)
# the 👆 cursor, an inline-SVG hand whose fingertip follows the pointer and presses in on down, and the reason
# outline: demoMark([[selector, n]…]) rings each target in --accent-2.
INIT = """(()=>{
  let s=11; Math.random=()=>{ s=s+0x6D2B79F5|0; let t=Math.imul(s^s>>>15,1|s); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; };
  addEventListener("DOMContentLoaded",()=>{
    const h=document.createElement("div"); h.id="demoHand";
    h.style.cssText="position:fixed;left:-21px;top:-3px;width:48px;height:60px;pointer-events:none;z-index:100;transform-origin:21px 3px;transition:scale .08s;filter:drop-shadow(0 2px 3px rgba(0,0,0,.3))";
    h.innerHTML='<svg viewBox="0 0 32 40" width="48" height="60" fill="#fff" stroke="#5b4a52" stroke-width="2" stroke-linejoin="round" stroke-linecap="round">'
      +'<path d="M11 24V5a3 3 0 0 1 6 0v10a3 3 0 0 1 6 0v2a3 3 0 0 1 6 0v9c0 7-4 12-11 12h-2c-5 0-8-3-10-7l-4-7a3 3 0 0 1 5-3z"/><path d="M17 15v6M23 17v5" fill="none"/></svg>';
    document.body.appendChild(h);
    addEventListener("pointermove",e=>{ h.style.translate=e.clientX+"px "+e.clientY+"px"; },true);
    addEventListener("pointerdown",()=>{ h.style.scale=".85"; },true);
    addEventListener("pointerup",()=>{ h.style.scale="1"; },true);
    const m=document.createElement("div"); m.id="demoMarks"; document.body.appendChild(m);
  });
  window.demoClear=()=>{ document.getElementById("demoMarks").innerHTML=""; };
  window.demoMark=ts=>{ demoClear();
    for(const [sel,n] of ts){ const b=document.querySelectorAll(sel)[n].getBoundingClientRect(), d=document.createElement("div");
      d.style.cssText="position:fixed;box-sizing:border-box;pointer-events:none;z-index:90;border-radius:10px;left:"+b.left+"px;top:"+b.top+"px;width:"+b.width+"px;height:"+b.height+"px;"
        +"border:3px solid var(--accent-2);box-shadow:0 0 0 1px rgba(91,74,82,.25),inset 0 0 0 1px rgba(91,74,82,.25)";
      document.getElementById("demoMarks").appendChild(d).animate({opacity:[0,1]},150); } };
})();"""


class Player:
    """The demo's hand: glides between targets and taps, holds, drags. Moves are ("method", *args) tuples."""

    def __init__(self, page, x, y):
        self.page, self.m, self.x, self.y = page, page.mouse, x, y

    async def to(self, t, secs=GLIDE):  # eased glide to the centre of target t (or a locator)
        loc = self.page.locator(t[0]).nth(t[1]) if isinstance(t, tuple) else t
        b, x0, y0 = await loc.bounding_box(), self.x, self.y
        self.x, self.y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        n = max(1, round(secs / 0.025))
        for k in range(1, n + 1):
            e = (1 - math.cos(math.pi * k / n)) / 2
            await self.m.move(x0 + (self.x - x0) * e, y0 + (self.y - y0) * e); await asyncio.sleep(secs / n)

    async def tap(self, loc, n=1):  # taps ≥60ms apart: the pages drop a click within 50ms of the last
        await self.to(loc)
        for _ in range(n):
            await self.m.down(); await asyncio.sleep(0.06); await self.m.up(); await asyncio.sleep(0.25)

    async def hold(self, loc, ms):
        await self.to(loc); await self.m.down(); await asyncio.sleep(ms / 1000); await self.m.up()

    async def drag(self, locs):
        await self.to(locs[0]); await self.m.down()
        for loc in locs[1:]:
            await self.to(loc, 0.45)
        await self.m.up()

    async def ring(self, loc, k):  # Catwalk: hold to open the ring, slide to slot k, let go
        await self.to(loc); await self.m.down(); await asyncio.sleep(0.4)
        await self.to(self.page.locator(".picker .cell").nth(k), 0.25); await self.m.up()


def cell(sel, n=0):  # a target: the n-th match of sel (Player resolves it to a locator, demoMark to a rect)
    return ("#board " + sel, n)


def steps_of(events, marks, play):
    """Group consecutive trace events with the same reason into steps (marks, moves); marks(evs) → targets, play(evs, marks) → moves."""
    steps = []
    for _, grp in itertools.groupby(events, key=lambda e: json.dumps(e[2], sort_keys=True)):
        evs = list(grp)
        mk = marks(evs)
        moves = play(evs, mk)
        if moves:
            steps.append((list(dict.fromkeys(mk)), moves))
    return steps


def tapper(events, N, tile, lines, marks, place, shown=()):
    """Catoku/Kattenratten/Catwalk: ✕ events become taps; ✕s that cover every still-empty tile of a line become one
    tap on its button (lines: (target, cells)). place(event, tile state) → the moves that play any other event."""
    grid = [2 if i in shown else 0 for i in range(N * N)]  # what the player sees: 0 empty, 1 ✕, 2 piece/rat/given

    def play(evs, mk):
        moves, xs = [], []
        def flush():
            while xs:
                full = [(b, L) for b, L in lines if len(e := [c for c in L if grid[c] == 0]) >= 2 and set(e) <= set(xs)]
                if full:
                    b, L = max(full, key=lambda bl: sum(grid[c] == 0 for c in bl[1]))
                    moves.append(("tap", b)); mk.extend([b] + [tile(c) for c in L])
                    for c in L:
                        if grid[c] == 0: grid[c] = 1; xs.remove(c)
                else:
                    c = xs.pop(0); grid[c] = 1; moves.append(("tap", tile(c)))
        for e in evs:
            if e[0] == "x":
                if grid[e[1]] == 0 and e[1] not in xs: xs.append(e[1])
            else:
                flush(); p = place(e, grid[e[1]]); placed.extend(p); moves += p; grid[e[1]] = 2
        flush()
        return moves
    placed = []; steps = steps_of(events, marks, play)
    while steps[-1][1][-1] not in placed:  # the last piece wins; ✕s after it would only play under the win card
        steps[-1][1].pop()
        if not steps[-1][1]: steps.pop()
    return steps


TRACE = "(()=>{ const ev=[]; %s; return ev; })()"  # the solver's deduction trace: [kind, at, why] in order
LOG = "(k,a,w)=>ev.push([k,a,w])"


async def catoku(page):
    """A cat goes down as soon as the board shows its row, column or region down to one open tile (the smallest such
    group is outlined), then its ✕s play in sub-steps (its row, column, region, then neighbours), each outlining the cat
    and that group; a locked-candidate step outlines its reason and the line or region it clears."""
    N, color = await page.evaluate("[state.N, state.puz.color]")
    tile = lambda i: cell(f'.cell[data-r="{i // N}"][data-c="{i % N}"]')
    rows = [[r * N + c for c in range(N)] for r in range(N)]
    cols = [[r * N + c for r in range(N)] for c in range(N)]
    reg = lambda g: [i for i in range(N * N) if color[i // N][i % N] == g]
    near = lambda i: [j for j in range(N * N) if abs(j // N - i // N) <= 1 and abs(j % N - i % N) <= 1]
    def part(i, w):  # which of the cat's groups ✕s tile i (place() ✕s row, column, region, neighbours in that order)
        r, c = w["cat"]
        return {"row": r} if i // N == r else {"col": c} if i % N == c else {"reg": color[r][c]} if color[i // N][i % N] == color[r][c] else {"near": r * N + c}
    trace = await page.evaluate(TRACE % f"logicalSolve(state.N,state.puz.color,{LOG})")
    groups = [({"row": r}, rows[r]) for r in range(N)] + [({"col": c}, cols[c]) for c in range(N)] + [({"reg": g}, reg(g)) for g in range(N)]
    free, cats, ev = [True] * (N * N), set(), []  # free: neither ✕ nor cat, as the player sees it
    order = lambda j, w: (["row", "col", "reg", "near"].index(next(iter(part(j, w)))), j)
    def settle():  # the solver ✕s a line's region before placing the line's last tile; the player places the cat first
        while f := min(((len(L), k, o[0]) for k, (w, L) in enumerate(groups) if not cats & set(L) and len(o := [i for i in L if free[i]]) == 1), default=None):
            i, w = f[2], {"cat": [f[2] // N, f[2] % N]}
            cats.add(i); free[i] = False; ev.append(("cat", i, groups[f[1]][0]))
            for j in sorted({j for j in rows[i // N] + cols[i % N] + reg(color[i // N][i % N]) + near(i) if free[j]}, key=lambda j: order(j, w)):
                free[j] = False; ev.append(("x", j, {**w, **part(j, w)}))
    for k, (r, c), w in trace:
        settle()
        if k == "x" and free[r * N + c]: free[r * N + c] = False; ev.append((k, r * N + c, w))
    settle()
    assert len(cats) == N, "catoku: the visible board never forces every cat"
    group = lambda w: rows[w["row"]] if "row" in w else cols[w["col"]] if "col" in w else reg(w["reg"]) if "reg" in w else near(w["near"])
    lines = [(cell(".hdr.row", r), rows[r]) for r in range(N)] + [(cell(".hdr.col", c), cols[c]) for c in range(N)]
    def marks(evs):
        w, at = evs[0][2], [i for _, i, _ in evs]
        if "cat" in w: return [tile(i) for i in group(w)]
        if evs[0][0] == "cat": return [tile(i) for i in group(w)]  # a single: the one open tile of its row, column or region
        if "reg" in w:  # the region sits in one row or column, so the rest of that line is cleared
            line = rows[at[0] // N] if all(i // N == at[0] // N for i in at) else cols[at[0] % N]
        else: line = reg(color[at[0] // N][at[0] % N])  # the row or column sits in one region, so the rest of it is cleared
        return [tile(i) for i in group(w) + line]
    return tapper(ev, N, tile, lines, marks, lambda e, s: [("tap", tile(e[1]), 2 - s)])


async def kattenratten(page):
    """Each cat plays outline → cat → the ✕s it rules out (its 8 neighbours, then any row or column it fills); the
    solver credits some of those to later rules, so they're pulled forward to follow their cat."""
    N, rat, counts = await page.evaluate("[state.N, [...state.puz.rat], state.puz.lines.map(l=>l.n)]")
    trace = await page.evaluate(TRACE % f"solve(state.puz,{LOG})")
    tile = lambda i: cell(f'.cell[data-cell="{i}"]')
    clue = lambda li: cell(f'button.clue.{"col" if li & 1 else "row"}[data-i="{li >> 1}"]')  # lines[li]: row li>>1, or its column if li&1
    line = lambda li: [j * N + (li >> 1) if li & 1 else (li >> 1) * N + j for j in range(N)]
    side = lambda i: [j for j in (i - N, i + N, i - 1 if i % N else -1, i + 1 if (i + 1) % N else -1) if 0 <= j < N * N]
    near = lambda i: [j for j in range(N * N) if j != i and abs(j // N - i // N) <= 1 and abs(j % N - i % N) <= 1]
    lines = [(clue(li), [c for c in line(li) if not rat[c]]) for li in range(2 * N)]
    seen, ev = [2 * r for r in rat], []  # what the player sees: 0 empty, 1 cat, 2 ✕ or rat
    for k, x, w in trace:
        if seen[x]: continue
        seen[x] = 1 if k == "cat" else 2; ev.append((k, x, w))
        if k != "cat": continue
        ev += [("x", y, {"cat": x}) for y in near(x) if not seen[y]]
        for y in near(x): seen[y] = seen[y] or 2
        for li in (2 * (x // N), 2 * (x % N) + 1):
            if sum(seen[c] == 1 for c in line(li)) == counts[li]:
                ev += [("x", c, {"line": li}) for c in line(li) if not seen[c]]
                for c in line(li): seen[c] = seen[c] or 2
    def marks(evs):
        _, at, w = evs[0]
        if "line" in w: return [clue(w["line"])] + [tile(i) for i in line(w["line"])]
        if "near" in w: return [tile(i) for i in [at] + side(at)]
        if "cat" in w: return [tile(i) for i in [w["cat"]] + near(w["cat"])]  # the cat and the tiles it touches
        if "rat" in w: return [tile(i) for i in [w["rat"]] + side(w["rat"])]  # the rat and its sides: one tile left
        return [tile(at)]
    return tapper(ev, N, tile, lines, marks, lambda e, s: [("tap", tile(e[1]), 2 - s)], {i for i in range(N * N) if rat[i]})


async def meowsweeper(page):
    """Flag (hold) and dig (tap) in trace order; a dig's flood is replayed so tiles it opened aren't tapped again.
    Each step outlines its clue(s) and the flags already around them — the count the clue has left to place."""
    N, num, rev = await page.evaluate("[state.N, [...state.puz.num], state.rev]")
    ev = await page.evaluate(TRACE % f"solve(state.N,state.puz.mines,state.puz.start,{LOG})")
    tile = lambda i: cell(f'.cell[data-cell="{i}"]')
    nbrs = lambda i: [r * N + c for r in range(i // N - 1, i // N + 2) for c in range(i % N - 1, i % N + 2)
                      if 0 <= r < N and 0 <= c < N and r * N + c != i]
    def play(evs, mk):
        moves = []
        for kind, i, _ in evs:
            if rev[i]: continue
            if kind == "flag": rev[i] = True; flags.add(i); moves.append(("hold", tile(i), 500)); continue
            moves.append(("tap", tile(i))); s = [i]
            while s:
                x = s.pop()
                if not rev[x]:
                    rev[x] = True
                    if num[x] == 0: s += nbrs(x)
        return moves
    flags = set()
    return steps_of(ev, lambda evs: [tile(i) for c in evs[0][2]["clue"] for i in [c] + [f for f in nbrs(c) if f in flags]], play)


async def purrlink(page):
    """Strands are drawn whole, cat to yarn, in the order the solver finishes them; each outlines its two ends first."""
    paths = await page.evaluate("state.puz.paths")
    ev = await page.evaluate(TRACE % f"solve(state.N,state.puz.ends,{LOG})")
    tile = lambda i: cell(f'.cell[data-i="{i}"]')
    strand = {c: k for k, p in enumerate(paths) for c in p}
    left, order = [len(p) - 1 for p in paths], []  # links still unforced per strand
    for _, (a, b), _ in ev:
        left[strand[a]] -= 1
        if not left[strand[a]]: order.append(strand[a])
    steps = [([tile(paths[k][0]), tile(paths[k][-1])], [("drag", [tile(c) for c in paths[k]])]) for k in order]
    last = steps[-1][1][0][1]; steps[-1][1][:] = [("drag", last[:-1]), ("drag", last[-2:])]  # the preview: one tile short
    return steps


async def catwalk(page):
    """✕s as taps (grouped into clue taps); a tile's piece is set from the ring (its links read off the solver's trace).
    The solver leans on facts the player can't mark (half-known links), so a move plays only once the visible board
    explains it — a full clue, a tile with under two open sides, or a tile that must be a paw with one piece that fits —
    outlined by that reason, and the trail grows from its ends the way players lay it."""
    N, locked, ring, masks, given = await page.evaluate("[state.N, state.locked.flat(), RING, PIECE_MASKS, state.grid.flat().map(v=>v>=2?PIECE_MASKS[v-2]:0)]")
    rc = await page.evaluate("[state.puz.rowCounts, state.puz.colCounts]")
    ev = await page.evaluate(TRACE % f"solve(state.N,state.puz.rowCounts,state.puz.colCounts,state.puz.entry,state.puz.exit,{LOG})")
    tile = lambda i: cell(f'.cell[data-r="{i // N}"][data-c="{i % N}"]')
    clue = lambda kind, i: cell(f'.clue.{kind}[data-i="{i}"]')
    rows = [[r * N + c for c in range(N)] for r in range(N)]
    cols = [[r * N + c for r in range(N)] for c in range(N)]
    lines = [(clue("row", r), rows[r]) for r in range(N)] + [(clue("col", c), cols[c]) for c in range(N)]
    mask, out = [0] * (N * N), []
    for kind, at, w in ev:  # links → a piece event as each tile's second link is forced
        if kind == "x": continue
        a, b = map(int, at.split("_"))
        for x, y in ((a, b), (b, a)):
            mask[x] |= {-N: 1, 1: 2, N: 4, -1: 8}[y - x]
            if not locked[x] and bin(mask[x]).count("1") == 2: out.append(("piece", x, w, ring.index(masks.index(mask[x]) + 2)))
    side = lambda i: [j for j in (i - N, i + N, i - 1 if i % N else -1, i + 1 if (i + 1) % N else -1) if 0 <= j < N * N]
    step, opp = {1: -N, 2: 1, 4: N, 8: -1}, {1: 4, 4: 1, 2: 8, 8: 2}
    nb = lambda x, d: -1 if d == 2 and x % N == N - 1 or d == 8 and x % N == 0 or not 0 <= x + step[d] < N * N else x + step[d]
    vis, pm = [2 if m else 0 for m in given], given[:]  # what the player sees: 0 ?, 1 ✕, 2 piece (pm its links)
    points = lambda y, d: y >= 0 and vis[y] == 2 and pm[y] & opp[d]
    opens = lambda x, d: (y := nb(x, d)) >= 0 and vis[y] != 1 and (vis[y] == 0 or bool(pm[y] & opp[d]))
    full = lambda w: rows[w["row"]] if "row" in w else cols[w["col"]]
    count = lambda w: rc[0][w["row"]] if "row" in w else rc[1][w["col"]]
    lines_of = lambda x: ({"row": x // N}, {"col": x % N})
    pointer = lambda x: next((y for d in (1, 2, 4, 8) if points(y := nb(x, d), d)), None)
    def why(e):  # the reason on the visible board, or None
        x = e[1]
        if e[0] == "x":
            w = next((w for w in lines_of(x) if sum(vis[i] == 2 for i in full(w)) == count(w)), None)
            return w or ({"cell": x} if pointer(x) is None and sum(opens(x, d) for d in (1, 2, 4, 8)) < 2 else None)
        fits = [m for m in masks if all(opens(x, d) if m & d else not points(nb(x, d), d) for d in (1, 2, 4, 8))]
        if len(fits) != 1: return None
        if pointer(x) is not None: return {"cell": x}
        return next((w for w in lines_of(x) if sum(vis[i] != 1 for i in full(w)) == count(w)), None)
    # players walk the trail from its ends: ✕s first, then the piece the last one points at, then any the trail points
    # at, and a piece out in space only when nothing else is explained
    fed = lambda x: last is not None and any(nb(last, d) == x and pm[last] & d for d in (1, 2, 4, 8))
    ends = lambda: [y for t in range(N * N) if vis[t] == 2 for d in (1, 2, 4, 8) if pm[t] & d and (y := nb(t, d)) >= 0 and not vis[y]]
    gap = lambda x: min((abs(x // N - y // N) + abs(x % N - y % N) for y in ends()), default=0)  # to the nearest trail end
    rank = lambda h, w: (0, json.dumps(w)) if h[0] == "x" else (1 if fed(h[1]) else 2 if "cell" in w else 3, gap(h[1]))  # a clue's ✕s together
    piece = {e[1]: e for e in out if e[0] == "piece"}
    held = list(piece.values()) + [("x", i, {}) for i in range(N * N) if not locked[i] and i not in piece]
    seq, last = [], None
    while held:
        ok = [(rank(h, w), k, h, w) for k, h in enumerate(held) if (w := why(h))]
        assert ok, f"catwalk: {len(held)} moves the board never explains — pick another seed"
        _, k, h, w = min(ok, key=lambda o: o[:2]); held.pop(k); seq.append((h[0], h[1], w, *h[3:]))
        if h[0] == "x": vis[h[1]] = 1
        else: vis[h[1]], pm[h[1]], last = 2, masks[ring[h[3]] - 2], h[1]
    out = seq
    def marks(evs):
        w = evs[0][2]
        if "row" in w: return [clue("row", w["row"])] + [tile(i) for i in rows[w["row"]]]
        if "col" in w: return [clue("col", w["col"])] + [tile(i) for i in cols[w["col"]]]
        return [tile(i) for i in [w["cell"]] + side(w["cell"])]  # degree: the tile and the sides that pin it
    return tapper(out, N, tile, lines, marks, lambda e, s: [("ring", tile(e[1]), e[3])], {i for i in range(N * N) if locked[i]})


ADAPTERS = {"purrlink": purrlink, "catoku": catoku, "kattenratten": kattenratten, "meowsweeper": meowsweeper, "catwalk": catwalk}


def encode(frames, end, out):
    """Screencast frames → a looping GIF on one shared palette (per-frame palettes make the pastels flicker)."""
    kept = []  # [timestamp, png]; a frame within GAP of the last kept one replaces its image
    for t, png in frames:
        if kept and (t - kept[-1][0] < GAP or png == kept[-1][1]): kept[-1][1] = png
        else: kept.append([t, png])
    imgs = [Image.open(io.BytesIO(png)).convert("RGB") for _, png in kept]
    durs = [round((b[0] - a[0]) * 1000) for a, b in zip(kept, kept[1:])] + [round((end - kept[-1][0]) * 1000)]
    sample = imgs[:: max(1, len(imgs) // 15)] + [imgs[-1]]  # spread over the run, plus the win card
    mosaic = Image.new("RGB", (SIZE * len(sample), SIZE))
    for k, im in enumerate(sample):
        mosaic.paste(im, (SIZE * k, 0))
    pal = mosaic.quantize(256, method=Image.Quantize.FASTOCTREE)  # median cut merges small accents (digits, flags) into their neighbours
    imgs = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    imgs[0].save(out, save_all=True, append_images=imgs[1:], duration=durs, loop=0, optimize=True)
    return sum(durs) / 1000, len(imgs)


async def record(browser, base, game):
    N, k = GAMES[game]
    seed = f"demo|{game}|{k}"
    ctx = await browser.new_context(viewport={"width": SIZE, "height": SIZE}, device_scale_factor=1)
    await ctx.add_init_script(INIT)
    page, errors = await ctx.new_page(), []
    page.on("pageerror", lambda e: errors.append(e))
    await page.goto(f"{base}/{game}/")
    await page.evaluate("([n,s])=>loadGame(n,s)", [N, seed])
    try:
        await page.wait_for_function("s=>state.seed===s&&!document.getElementById('board').classList.contains('busy')", arg=seed, timeout=30000)
    except Exception:
        raise SystemExit(f"{game}: board {seed} didn't load {errors}")
    await page.evaluate("document.getElementById('rulesOverlay').classList.remove('show')")
    await page.wait_for_load_state("networkidle")  # the emoji SVGs, prefetched after load
    await page.mouse.move(SIZE - 60, SIZE - 40)  # the hand rests off the board until the first move
    steps, player = await ADAPTERS[game](page), Player(page, SIZE - 60, SIZE - 40)

    await page.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")  # paint the loaded board first, or the screencast opens on a stale frame
    cdp, frames = await ctx.new_cdp_session(page), []
    def frame(p):
        frames.append((p["metadata"]["timestamp"], base64.b64decode(p["data"])))
        asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]}))
    cdp.on("Page.screencastFrame", frame)
    await cdp.send("Page.startScreencast", {"format": "png", "maxWidth": SIZE, "maxHeight": SIZE})
    await asyncio.sleep(1.5)
    hide = "['demoHand','demoMarks'].forEach(id=>document.getElementById(id).style.visibility='%s')"
    for si, (marks, moves) in enumerate(steps):
        await page.evaluate("m=>demoMark(m)", marks); await asyncio.sleep(MARK)
        for i, (m, *a) in enumerate(moves):
            if si == len(steps) - 1 and i == len(moves) - 1:
                t0 = time.time(); await page.evaluate(hide % "hidden"); preview = await page.screenshot()
                await page.evaluate(hide % "visible"); t1 = time.time() + 0.1  # the hidden-hand frames stay out of the GIF
            await getattr(player, m)(*a)
        if si < len(steps) - 1: await asyncio.sleep(PAUSE)  # the winning step's outline clears before the win card
        await page.evaluate("demoClear()")
    if not await page.evaluate("state.won"):
        raise SystemExit(f"{game}: the moves didn't win {errors}")
    await asyncio.sleep(4)
    await cdp.send("Page.stopScreencast")
    end = time.time()
    await ctx.close()

    gif = ROOT / "assets" / f"{game}-demo.gif"
    frames = [f for f in frames if not t0 <= f[0] <= t1]
    secs, n = encode(frames, max(end, frames[-1][0] + 0.1), gif)
    Image.open(io.BytesIO(preview)).save(ROOT / "assets" / f"{game}-preview.png", optimize=True)
    warn = "" if 20 <= secs <= 60 else "  (outside 20-60s!)"
    print(f"{game}: {secs:.1f}s, {n} frames, {gif.stat().st_size / 1e6:.2f} MB{warn}")


async def main(games):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)  # not localhost: that runs every game's self-test
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=CHROME)
        for game in games:
            await record(browser, base, game)
        await browser.close()
    server.shutdown()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(GAMES)))
