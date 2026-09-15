# Catoku

A "Queens"-style logic puzzle with cats: place one cat per row, per column, and
per color region; no two cats touch (including diagonally). Puzzles are
deterministic per seed and solvable by pure deduction — no guessing.

The whole game is one file: `catoku/index.html` (`<style>`, HTML, one
`<script>`). No framework, dependencies, or build step. It runs client-side.
The only persistence is `localStorage` key `catoku_v1` (best win time per board
size + solved count — never the puzzle).

## Architecture

The `<script>` runs top-to-bottom in commented sections: deterministic RNG →
puzzle generation → config → date → storage → state → render → interaction →
timer → stats → wire-up → console self-test.

- **Deterministic puzzles.** Seed with `makeRng` (`xmur3` + `mulberry32`). The
  daily board uses seed `"YYYY-MM-DD|7"`; "New game" uses a fresh
  `"rnd|N|counter|Date.now()"` seed. Puzzles are memoized in `puzzleCache` and
  rebuilt on every page load.
- **Generation** (`generatePuzzle`): pick a solution (`genPlacement`), then
  `carveColoring` reshapes color regions, hill-climbing on how far the deductive
  solver gets, until the board is fully deducible.
- **Deductive solver** (`logicalSolve`): human-style inference only (forced
  singles per row/col/region + locked-candidate confinement), no backtracking.
  Returns `{placed, placement}`; `placed===N` means fully deducible.
- **Board size is the difficulty**: 4–12, default 7 (`DEFAULT_N`). `MAX_N=12`;
  larger boards fall back and take seconds.

## Rules

Keep in sync: the constraints (distinct row/col/color + no 8-directional
adjacency) are encoded in four places — `genPlacement`, `logicalSolve`,
`countSolutions`, and `conflicts`. Change a rule in all four or they disagree.

## Visual style

Shared look across Kattenspellen games. Keep new games consistent with this.

- **Mood**: soft, playful, pastel. Cats and emoji, never harsh.
- **Font**: `"Nunito","Segoe UI",system-ui,-apple-system,sans-serif`.
- **Background**: cream-to-lilac gradient, `linear-gradient(160deg,#fdf6f0,#f5eefb)`.
- **Palette**:
  - `--ink: #5b4a52` — text (soft mauve, not black).
  - `--panel: #ffffff` — cards.
  - `--accent: #f7a8c4` — pink, for headings/highlights.
  - `--accent-2: #3f8fd6` — blue, for primary buttons.
- **Shape**: generous rounding (cards ~20px, buttons/cells ~8–12px) and soft
  shadows, `0 6px 20px rgba(120,90,110,.15)`.
- **Motion**: small, springy. Hover lifts (`translateY(-2px…-4px)`), press
  scales down, wins pop.
- **Game regions**: a 12-color pastel palette — even 30° hue sweep with a
  lightness zigzag so all pairs stay distinct (ΔE ≥ 18) even when touching.
  Any glyph drawn on a region (e.g. the ✕ mark) must clear 3:1 contrast against
  every region color.

## Code style

- Vanilla ES, `"use strict"`, 2-space indent, semicolons.
- Terse and compact: multiple statements per line are fine, short helper names,
  inline arrow helpers. Match the surrounding density.
- Section headers use `/* ---------- name ---------- */`.
- Never call `Math.random()` or `Date.now()` inside puzzle generation — thread
  the seeded `rng` through instead. `Math.random()` is fine for cosmetic-only
  choices (e.g. which cat emoji renders).

## Build, test, run

No build — open or serve `catoku/index.html`.

Run a static server, then hard-refresh (Ctrl+F5) to pick up changes:

```bash
python -m http.server 80    # http://localhost/
```

`runSelfTest()` logs to the browser console on `localhost` or when the URL ends
in `#selftest`: it regenerates sizes `4,5,7,9,12`, asserts constraints, and
reports solvability. Every size should print "logically solvable ✅"; "fell
back at k/N" means the carver missed full deduction (raise the retry count or
`maxIter` in `generatePuzzle`).

Headless check (Node with a stubbed DOM):

```bash
node -e '
const fs=require("fs"), vm=require("vm");
const js=fs.readFileSync("catoku/index.html","utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
const dummy=new Proxy(function(){},{get:(t,p)=>p==="length"?0:dummy,apply:()=>dummy,set:()=>true});
const box={console,Math,Date,JSON,Array,Set,String,Object,window:dummy,document:dummy,
  location:{hostname:"localhost",hash:""},
  localStorage:{getItem:()=>null,setItem:()=>{}},requestAnimationFrame:()=>{},setInterval:()=>{},clearInterval:()=>{}};
vm.createContext(box); vm.runInContext(js, box, {filename:"catoku.js"});'
```

## Deploy

`.github/workflows/deploy.yml` uploads the repo root to GitHub Pages when a
release is published: `kattenspellen.github.io/games/` is the landing,
`.../games/catoku/` is the game.
