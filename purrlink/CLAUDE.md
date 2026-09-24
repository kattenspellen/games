# Purrlink

A "Numberlink"/"Flow"-style logic puzzle with cats: connect each cat 🐱 to its ball of yarn 🧶 (same colour) with a strand. Strands never cross or branch, and together they fill every square. Puzzles are deterministic per seed and solvable by pure deduction.

See the repo-root `CLAUDE.md` for the shared Kattenspellen criteria (single-file delivery, seeded generation, self-test, visual style, deploy). This file is the Purrlink-specific detail.

## Architecture

The `<script>` runs top-to-bottom in commented sections: deterministic RNG → puzzle generation → config → date → storage → state → render → interaction → timer → stats → wire-up → console self-test.

- **Deterministic puzzles.** Seed with `makeRng` (`xmur3` + `mulberry32`). The daily board uses seed `"YYYY-MM-DD|purrlink"`; "New game" uses a fresh `"rnd|N|counter|Date.now()"` seed. Puzzles are memoized in `puzzleCache`.
- **Generation** (`generatePuzzle`): `hamPath` builds a random Hamiltonian path (serpentine + backbite moves); `genPaths` cuts it into `N-3` strands of length ≥ `MIN_LEN` (3) — a full-cover solution. Then, while the direct rules (`propagate`) stall, split a strand at a cell they couldn't pin down: the new cat+yarn pair adds clues exactly where the ambiguity is. Random cuts alone are almost never unique past 6×6 — the split repair is what makes larger boards work. Splits hand out easy clues, so `mergePaths` then joins strands whose ends touch, keeping each join only if `solve` (with contradiction) still completes — fewer, longer strands. A join that failed isn't retried after later joins (failed solves dominate gen time). **Every served board needs ≥1 contradiction step**: if the direct rules alone finish the merged board, restart. Splits may overshoot to 2× `maxPairs(N)`; restart if merging can't land within it. `maxPairs` is 12 up to 9×9 (the cap filters toward fewer pairs, i.e. harder) and the full 16-colour palette at 10×10. Which end is the cat and the colour assignment are also drawn from `rng`. Throws (never serves) if 2000 restarts find nothing; self-test and benchmarks never hit that.
- **Deductive solver** (`solve`): edge-based; each edge is on/off/unknown and each cell carries a bitmask of possible colours. `propagate` applies the direct rules to a fixpoint: **degree** (endpoint links 1, every other cell 2 — the fill rule), **colour** (linked cells share a colour; cells with no common colour can't link), **no loops** (never link two already-joined cells), **reach** (colour c survives in a cell only if c's cat can reach it and it has ≥2 c-capable open sides). When they stall, `solve` adds one-level **proof by contradiction**: assume an open edge on (or off), `propagate` from the current state; if that dies, the opposite is proven. The assumption never nests. `steps` counts contradictions used; `complete` ⇒ every edge forced ⇒ unique.
- **The player draws strands** (`state.paths[k]` = cell list from one endpoint). Press an endpoint to restart its strand (a tap clears it), or a strand cell to trim there; dragging extends, re-entering trims, crossing another strand cuts it. Fast drags step greedily toward the pointer. Undo = one snapshot per stroke. The board starts with only the endpoints — the solver's start state.
- **Board size is the difficulty**: 5–10, default 6 (`DEFAULT_N`). Pair count falls out of generation (~3–4 at 5×5, ~9 at 8×8, ~11 at 9×9, ~14 at 10×10). Gen (desktop): 8×8 ~110ms median, ~500ms worst; 9×9 ~340ms / ~1.2s; 10×10 ~650ms / ~1.4s — the slowest in the repo, and the contradiction pass is the cost (a failed merge exhausts every probe). 10×10 on a 12-colour cap averaged ~7s — the palette was the limit there.

## Rules

Keep in sync: the rules (endpoints link once, every other cell twice / every square filled, one colour per strand, no crossing, no loops) live in `propagate` (deductive proof), `genPaths` (full-cover, ≥ `MIN_LEN` strands) and the player-side `extend` + `isSolved` (strands own cells exclusively; win = every pair `linked` and all N² cells covered). Uniqueness is what lets `isSolved` check rules instead of comparing to the stored solution — self-test asserts the generator's solution passes it. Change a rule in all of them or they disagree.

## Signature palette

Peach `--accent:#f4a582` is the signature (`theme-color`, page gradient), and yarn pink `--accent-2:#d81b60` — the Noto 🧶's own shade — drives the primary button, share chip, and stats. The landing-tile `<h2>` is a dark plum `#6b3fa0`, a deep shade of the gradient's pale plum. The board frame is a pale pink `#f8d3e1`; size input and stats chips a paler pink `#fce4ee`. The page gradient runs pale peach `#fdf0e8` → pale plum `#f3edfb` — Catoku-level lightness so the colourful grid isn't overwhelming, and a deliberate exception to the family's fixed cream start so both accents show; the overlay scrim is a dark peach `rgba(90,55,40,.4)`.

Strands use 16 `COLORS`, all pairs ΔE76 ≥ 22 (same metric as Catoku's regions); the last four (olive, sage, lavender, mauve) were added for 10×10. Covered cells get a 22% tint of their strand colour. Endpoints are Catwalk-style light tiles — a 40% tint ringed in the solid strand colour, bars showing through — holding the emoji. Each endpoint also carries a small white pair-number badge (`.bd`, top-left) — at up to 16 pairs colour alone isn't enough, especially for colour-blind players. A linked pair's cat turns 😻.

## Persistence

`localStorage` key `purrlink_v1`: best win time per board size + solved count — never the puzzle.

## Self-test

`runSelfTest()` regenerates every size `5`–`10`, asserts strands cover every cell once with neighbour steps and length ≥ 3, the pair count fits `maxPairs(N)`, the generator's solution passes `isSolved`, re-solving from the bare endpoints is complete with deduced links equal to the generator's strands, and the direct rules alone are *not* complete (≥1 contradiction step). Every size should print "logically solvable ✅ (k contradiction steps)".

Headless check (Node with a stubbed DOM):

```bash
node -e '
const fs=require("fs"), vm=require("vm");
const js=fs.readFileSync("purrlink/index.html","utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
const dummy=new Proxy(function(){},{get:(t,p)=>p==="length"?0:dummy,apply:()=>dummy,set:()=>true});
const box={console,Math,Date,JSON,Array,Set,Map,String,Object,window:dummy,document:dummy,
  location:{hostname:"localhost",hash:""},
  localStorage:{getItem:()=>null,setItem:()=>{}},requestAnimationFrame:()=>{},setInterval:()=>{},clearInterval:()=>{},setTimeout:()=>{}};
vm.createContext(box); vm.runInContext(js, box, {filename:"purrlink.js"});'
```
