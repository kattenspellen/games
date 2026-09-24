# Catwalk

A "Train Tracks"-style logic puzzle with cats: lay a single connected trail of cat paws from the entry nub to the exit nub. The trail never branches, crosses, or loops — each paw links exactly two of its four sides — and each row/column holds exactly its clue count. Puzzles are deterministic per seed and solvable by pure deduction.

See the repo-root `CLAUDE.md` for the shared Kattenspellen criteria (single-file delivery, seeded generation, self-test, visual style, deploy). This file is the Catwalk-specific detail.

## Architecture

The `<script>` runs top-to-bottom in commented sections: deterministic RNG → puzzle generation → config → date → storage → state → render → interaction → timer → stats → wire-up → console self-test.

- **Deterministic puzzles.** Seed with `makeRng` (`xmur3` + `mulberry32`). The daily board uses seed `"YYYY-MM-DD|catwalk"`; "New game" uses a fresh `"rnd|N|counter|Date.now()"` seed. Puzzles are memoized in `puzzleCache`.
- **Generation** (`generatePuzzle`): `genPath` draws a random self-avoiding walk from one border cell (entry) to another (exit), each with an off-grid stub; `pathData` derives the row/column clue counts and the solution cell/edge sets. Retry fresh paths until the solver proves one uniquely deducible.
- **Deductive solver** (`solve`): edge-based constraint propagation, no backtracking. Each grid edge is on/off/unknown; every cell ends at degree 0 (empty) or 2 (paw). Two rule families: **degree** (a paw forces/forbids edges once its on/possible counts pin it) and **counts** (a row/col whose known paws meet its clue empties the rest; one whose paws+unknowns equal its clue fills them). Returns `{dead, complete, tracks, state}`; `complete && !dead` means fully deducible (hence unique).
- **Oriented pieces are the player's input** (as in the original). A cell cycles unknown → ✕ → the 6 track pieces (2 straights, 4 elbows) → unknown; each piece links 2 of its 4 sides. `state.grid` holds `0` unknown, `1` ✕, `2+i` for `PIECE_MASKS[i]` (a 2-bit link mask). Entry/exit are given, locked, fully oriented (off-grid stub + the one in-grid link, both read from `solEdges`). Cells-only input was ambiguous at 3+neighbour junctions (a cell's shape isn't fixed by membership alone); oriented pieces close that.
- **Board size is the difficulty**: 4–9, default 6 (`DEFAULT_N`). All sizes stay fully deducible; larger boards are rarer to land on a deducible layout, so `generatePuzzle` scales its retry budget (2500 for N≥8). 9×9 gen is ~45ms median, ~170ms worst-case — still well under a second and never a fall-back.

## Rules

Keep in sync: the constraints (each paw degree 2, one connected path, row/col counts) are encoded in three places — `solve` (deductive), `pathData` (clue derivation) and `conflicts` (player-facing over-count highlight only). The win check (`checkWin`) compares the player's *realized links* (`realizedEdges` — an edge exists only where both cells' pieces point at each other) to the unique solution's `solEdges`; matching edges force every piece's shape, one connected trail, and the counts at once. Change a rule in all of them or they disagree. Note: paw *adjacency* is deliberately not a conflict — two path segments may run alongside each other, so a paw can touch 3+ paws while only linking two; branching is a property of links, not marked cells.

## Signature palette

Catwalk's two accents are adjacent on the wheel: green `--accent:#7cc47f` is the signature (paw-cell fill, headings, `theme-color`), and teal `--accent-2:#2b9d9d` is the second hue driving the primary button, trail bars/links, endpoint stubs, and locked ring — so the green cell + teal trail reads as a two-tone tile. Teal sits between green and cyan, so the 🐾 emoji (cyan on Android, brown on Apple — font-rendered, not CSS-colorable) lands inside the scheme rather than clashing. Paw cells fill with a light teal (`#cbe9e8`, a pale tint of `--accent-2`) so the teal trail bars read clearly on them; empty (✕) cells are a pale green, unknown cells white.

## Persistence

`localStorage` key `catwalk_v1`: best win time per board size + solved count — never the puzzle.

## Self-test

`runSelfTest()` regenerates every size `4`–`9`, asserts clue counts match the solution, endpoints sit on the border, and (when fully deducible) the deduced trail matches the generator's. Every size should print "logically solvable ✅"; "fell back ⚠️" means no deducible board was found in the retry budget (raise `retries` in `generatePuzzle`).

Headless check (Node with a stubbed DOM):

```bash
node -e '
const fs=require("fs"), vm=require("vm");
const js=fs.readFileSync("catwalk/index.html","utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
const dummy=new Proxy(function(){},{get:(t,p)=>p==="length"?0:dummy,apply:()=>dummy,set:()=>true});
const box={console,Math,Date,JSON,Array,Set,Map,String,Object,window:dummy,document:dummy,
  location:{hostname:"localhost",hash:""},
  localStorage:{getItem:()=>null,setItem:()=>{}},requestAnimationFrame:()=>{},setInterval:()=>{},clearInterval:()=>{}};
vm.createContext(box); vm.runInContext(js, box, {filename:"catwalk.js"});'
```
