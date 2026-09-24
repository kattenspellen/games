# Catoku

A "Queens"-style logic puzzle with cats: place one cat per row, per column, and
per color region; no two cats touch (including diagonally). Puzzles are
deterministic per seed and solvable by pure deduction.

See the repo-root `CLAUDE.md` for the shared Kattenspellen criteria (single-file
delivery, seeded generation, self-test, visual style, deploy). This file is the
Catoku-specific detail.

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

## Signature palette

Catoku's accents are pink `--accent:#f7a8c4` and blue `--accent-2:#3f8fd6` (the
primary button); emoji 🐱. Regions use a 12-color pastel palette — an even 30°
hue sweep with a lightness zigzag so all pairs stay distinct (ΔE ≥ 18) even when
touching. Any glyph drawn on a region (the ✕ mark) must clear 3:1 contrast
against every region color.

## Persistence

`localStorage` key `catoku_v1`: best win time per board size + solved count —
never the puzzle.

## Self-test

`runSelfTest()` regenerates sizes `4,5,7,9,12`, asserts constraints, and reports
solvability. Every size should print "logically solvable ✅"; "fell back at k/N"
means the carver missed full deduction (raise the retry count or `maxIter` in
`generatePuzzle`).

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
