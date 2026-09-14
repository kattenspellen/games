# Catoku

A "Queens"-style logic puzzle with cats. Place one cat 🐱 per row, per
column, and per color region; no two cats may touch (including diagonally).
Puzzles are deterministic per seed and generated to be **solvable by
pure deduction** — no guessing. On load you get a daily 7×7 board; "New game"
rerolls at any size 4–12 (`MIN_N`/`MAX_N`).

## Architecture

The game is one self-contained file: **`catoku/index.html`** (`<style>`, HTML, and
a single `<script>`). No framework, no dependencies, no build step, no bundler.
Runs entirely client-side. Only persistence is `localStorage` key `catoku_v1`,
which stores the best win time per board size + a solved count — never the
puzzle itself.

The repo is a **hub**: root `index.html` is a static landing page linking to
each game; `catoku/index.html` is the game. Deployed to GitHub Pages by
`.github/workflows/deploy.yml` (uploads the repo root as-is) when a release is
published — so `kattenspellen.github.io/games/` is the landing and
`.../games/catoku/` is the game.

The `<script>` is organized top-to-bottom into commented sections:
deterministic RNG → puzzle generation → config → date → storage → state →
render → interaction → timer → stats → wire-up → console self-test.

### Key concepts
- **Deterministic puzzles.** Seeded via `makeRng` (`xmur3` + `mulberry32`).
  The default board uses seed `"YYYY-MM-DD|7"` (same daily 7×7 for everyone);
  "New game" uses a fresh `"rnd|N|counter|Date.now()"` seed. Puzzles are memoized
  in the in-memory `puzzleCache` (keyed by seed) and rebuilt on every page load.
  `MAX_N=12` — larger boards fall back (not fully deducible) and take seconds.
- **Generation** (`generatePuzzle`): pick a solution (`genPlacement`), then
  `carveColoring` reshapes color regions — hill-climbing on how far the
  deductive solver gets — until the board is fully deducible. Random colorings
  are ~never logic-solvable at N≥7, so carving is the mechanism, not filtering.
- **Deductive solver** (`logicalSolve`): human-style inference only (forced
  singles per row/col/region + locked-candidate confinement), no backtracking.
  Returns `{placed, placement}`; `placed===N` means fully deducible (⟹ unique).
- **Board size is the difficulty**: user-selectable 4–12, default 7
  (`DEFAULT_N`). `generatePuzzle` scales its carving budget for N>9.

### The constraint model is duplicated — keep it in sync
The rules (distinct row/col/color + no 8-directional adjacency) are encoded in
**four** places: `genPlacement`, `logicalSolve`, `countSolutions`, and
`conflicts`. Any rule change must touch all four or they'll disagree.

## Code style

- Vanilla ES, `"use strict"`, 2-space indent, semicolons.
- Terse and compact: multiple statements per line are normal
  (`for(...){ ... }` on one line), short helper names, arrow helpers inline.
- Section headers use `/* ---------- name ---------- */`.
- Match the surrounding density — don't expand compact code into verbose blocks.
- Determinism matters: never call `Math.random()`/`Date.now()` inside puzzle
  generation — thread the seeded `rng` through instead. (`Math.random()` is fine
  for cosmetic-only choices like which cat emoji renders.)

## Build

None. It's a static file — open or serve `catoku/index.html` directly.

## Testing

`runSelfTest()` logs to the browser console: it regenerates a spread of board
sizes (`4,5,7,9,12`), asserts the solution satisfies all constraints, and
reports whether each is fully logic-solvable. It's gated to dev only — it runs
on `localhost` or when the URL ends in `#selftest`, so Pages visitors don't pay
the ~1s regen.

Headless check (no browser) — extract and run the script under Node with a
stubbed DOM:

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

Expect every tested size to print "logically solvable ✅". If a board
prints "fell back at k/N", the carver didn't reach full deduction within budget
— raise the retry count or `maxIter` in `generatePuzzle`, or strengthen
`logicalSolve` with an extra technique.

## Local development

It's a static file; any static server works.

```bash
python -m http.server 80    # then http://desktop-tome18.local/  (mDNS) or http://localhost/
```

- Puzzles regenerate on every page load, so a browser refresh picks up code
  changes. Hard-refresh (Ctrl+F5) to defeat HTTP caching of `catoku/index.html`.
- Serving on `0.0.0.0` (the default) makes it reachable on the LAN via the
  machine's `<hostname>.local` (Windows 11 answers mDNS for its own hostname).
  First external connection may trigger a Windows Firewall prompt — allow on
  private networks.
