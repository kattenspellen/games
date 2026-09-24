# Meowsweeper

A "Minesweeper"-style logic puzzle with cats: clear every safe tile without digging up one of the spooky things that scare the cats. Numbers count adjacent spooky things; use them to deduce the rest. Every board is deterministic per seed and — unlike classic minesweeper — solvable by **pure deduction** (see below).

See the repo-root `CLAUDE.md` for the shared Kattenspellen criteria (single-file delivery, seeded generation, self-test, visual style, deploy). This file is the Meowsweeper-specific detail.

## The deducibility invariant (the whole point)

Classic minesweeper often leaves a coin flip — that violates the repo's hard invariant. So Meowsweeper only ever serves boards a deductive solver can fully crack. `generatePuzzle` retries fresh random mine layouts until `solve` proves the board is completely deducible from the opening; a layout that isn't is discarded, never served. At 15% density (`DENSITY`) the fall-back is never hit in practice — see self-test.

## Architecture

The `<script>` runs top-to-bottom in commented sections: deterministic RNG → puzzle generation → config → date → storage → state → render → interaction → timer → stats → wire-up → console self-test.

- **Deterministic puzzles.** Seed with `makeRng` (`xmur3` + `mulberry32`). The daily board uses seed `"YYYY-MM-DD|meowsweeper"`; "New game" uses a fresh `"rnd|N|counter|Date.now()"` seed. Puzzles are memoized in `puzzleCache`.
- **Generation** (`generatePuzzle`): pick a random start, keep its 3×3 mine-free (so the first dig is a blank that floods), scatter `M = round(N²·DENSITY)` mines over the rest, and run the solver. Return the first layout proven fully deducible; keep the most-revealed as a fallback (self-test asserts it's never needed). Generation is sub-millisecond — no size scaling problem.
- **Deductive solver** (`solve`): simulate a player who only makes proven moves. Reveal the blank start, flood its zero-region, then propagate to a fixpoint with two rule families: **count** (a clue whose remaining mines equal its unknown neighbours flags them all; one whose remaining is 0 clears them all) and **subset / the 1-2 rule** (if clue A's unknowns are a strict subset of clue B's, the difference set is forced all-mine or all-safe). No backtracking. `complete` ⇒ every safe cell was deduced.
- **The player digs and flags** the same board the solver reasoned about. `dig` floods zero-regions exactly like the solver; a flag is a pure marker. Digging a mine loses (a player who only makes proven moves never has to).
- **Opening region pre-revealed on load.** `setupGame` calls `floodOpen(start)` before rendering, so the board loads showing the same opening region + numbers the solver starts from — no first-dig death, and the served board matches the deductive proof from tile one. Generation also rejects boards whose opening flood already reveals every safe cell (they'd need no real dig).
- **Board size is the difficulty**: 5–10, default 8 (`DEFAULT_N`). Density is fixed, so a bigger grid means more tiles and more mines to reason about.

## Rules

Keep in sync: the reveal/flood + mine-count rules live in three places — `solve` (deductive generation proof), `dig`/`checkWin` (player-side reveal + flood + win), and the `num` derivation (adjacent-mine counts, computed in both `solve` and the self-test). The number under a cell is its count of 8-neighbour mines; a 0 floods; win = every non-mine cell revealed. Change a rule in all of them or they disagree.

## Signature palette

Lavender `--accent:#b39ddb` is the signature (headings, `theme-color`, landing-tile `<h2>` — overridden to a readable `#7c6bb0` on white), and blue `--accent-2:#5b8dee` is the second hue driving the primary button, flag tiles, and the covered-tile edge — a two-tone lavender/blue scheme. The page background gradient runs cream `#fdf6f0` → a pale blue tint of `--accent-2` (`#e7eeff`); the overlay scrim stays a lavender-accent tint per repo convention. Covered tiles are a raised pale lavender (`#e6def5`); revealed tiles a flat near-white (`#f7f3fd`); revealed mines on a loss are a red tint. Number glyphs use the classic distinct per-digit colours (`NUMCOL`), all clearing 3:1 contrast on the light revealed tile. The spooky "mines" are emoji (`SPOOKY` — 🤡👻👽🧟🐍🦠⛈️☄️🎃🧨🛸💉💥☢️), assigned per-mine at load from a shuffled bag (distinct until all 14 are used, `Math.random`, cosmetic only); representative emoji / favicon is 🙀 (a spooked cat).

## Persistence

`localStorage` key `meowsweeper_v1`: best clear time per board size + solved count — never the puzzle.

## Self-test

`runSelfTest()` regenerates every size `5`–`10`, asserts the start 3×3 is mine-free, the `num` counts match the mine layout, and (re-solving) that every served board is fully deducible with its deduced safe cells matching the real ones. Every size should print "logically solvable ✅"; "fell back ⚠️" means no fully deducible board was found in the retry budget (raise `retries`/lower `DENSITY` in `generatePuzzle`).

Headless check (Node with a stubbed DOM):

```bash
node -e '
const fs=require("fs"), vm=require("vm");
const js=fs.readFileSync("meowsweeper/index.html","utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
const dummy=new Proxy(function(){},{get:(t,p)=>p==="length"?0:dummy,apply:()=>dummy,set:()=>true});
const box={console,Math,Date,JSON,Array,Set,Map,String,Object,window:dummy,document:dummy,
  location:{hostname:"localhost",hash:""},
  localStorage:{getItem:()=>null,setItem:()=>{}},requestAnimationFrame:()=>{},setInterval:()=>{},clearInterval:()=>{},setTimeout:()=>{}};
vm.createContext(box); vm.runInContext(js, box, {filename:"meowsweeper.js"});'
```
