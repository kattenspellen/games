# Kattenratten

A "Tents"-style logic puzzle with cats: every rat 🐭 gets its own cat 🐱, sitting directly above, below, left or right of it. Cats never touch, not even diagonally (two that do hiss 😾), and the numbers outside the grid say how many cats each row and column holds. Puzzles are deterministic per seed and solvable by pure deduction.

See the repo-root `CLAUDE.md` for the shared Kattenspellen criteria (single-file delivery, seeded generation, self-test, visual style, deploy). This file is the Kattenratten-specific detail.

## Architecture

The `<script>` runs top-to-bottom in commented sections: deterministic RNG → puzzle generation → config → date → storage → state → render → interaction → timer → stats → challenge links → wire-up → console self-test.

- **Deterministic puzzles.** Seed with `makeRng` (`xmur3` + `mulberry32`). The daily board uses seed `"YYYY-MM-DD|kattenratten"`; "New game" uses a fresh `"rnd|N|counter|Date.now()"` seed. Puzzles are memoized in `puzzleCache`.
- **Board model.** A cell id is `r*N+c`. `rat[cell]` marks a rat; `rowCounts`/`colCounts` are the clues (all shown, as in classic Tents). `a4`/`a8` are each cell's side / all-8 neighbours; `lines` is every row and column with its count. `pair` (rat → cat) is the generator's pairing, used only by the self-test.
- **Generation** (`generatePuzzle`): walk the cells in shuffled order, placing a cat wherever none of its 8 neighbours is a cat and it isn't a rat, and turning a random free side-neighbour into its rat; stop at `DENSITY` (20%) of the board as cats. Derive the counts. Keep the board only if `solve` completes from the bare board; throws (never serves) after 500 tries — self-test never hits it. Gen (Node, 20 seeds): 7×7 ~0.1ms median, 10×10 ~0.2ms, 12×12 ~0.5ms / ~7ms worst. Contradiction steps median/max: 7×7 0/1, 10×10 1/5, 12×12 1/10.
- **Deductive solver** (`solve`): cell states unknown / cat / no-cat (rats start as no-cat). `propagate` applies the direct rules to a fixpoint: **no touch** (a cat empties its 8 neighbours; touching cats = dead), **counts** (n cats placed empties the rest of the line; cats + unknowns = n fills them; over/under = dead), **pairing** (rebuilt each pass: a cat with exactly one side rat no other cat holds claims it, none = dead; a rat whose only candidate is an unpaired cat is that cat's; a rat with no candidate = dead, a single unknown candidate becomes a cat; an unknown whose side rats are all held — or that has none — is no-cat). When they stall, one-level **proof by contradiction**: assume a cell is (or isn't) a cat, `propagate`; if it dies, the opposite is proven. Never nests. `complete` ⇒ every cell forced ⇒ unique. The solver starts from the bare board — exactly what the player is handed.
- **The player taps** a non-rat square: empty → ✕ note → cat → empty (Catoku's cycle). Tapping a row/column number ✕s that line's empty squares, or clears its ✕s if none are empty (Catwalk's `fillLine`). Undo = one snapshot per action (last 10, Ctrl+Z).
- **Board size is the difficulty**: 5–12, default 7 (`DEFAULT_N`). Cat density is fixed, so a bigger yard means more cats and more contradiction steps. `MAX_N` is bounded by screen width (13 columns at the 24px cell floor fit a 375px phone), not generation time — even 16×16 generates in ~110ms worst.

## Rules

Keep in sync: the rules (each rat has its own side-adjacent cat, one-to-one; cats never touch, including diagonally; each row/column holds exactly its count) live in `generatePuzzle` (builds a valid pairing), `propagate` (deductive proof), `isSolved` (win: counts exact, no touching, and a perfect cat↔rat matching by Kuhn's augmenting paths) and `conflicts` (player highlights: touching cats, cats with no rat beside them, over-full lines). The player places cats only; pairing is implicit. Uniqueness is what lets `isSolved` check rules instead of comparing to the stored solution — self-test asserts the generator's cats pass it. Change a rule in all of them or they disagree.

## Signature palette

Amber `--accent:#f5b041` is the signature (`theme-color`), and rat-ear pink `--accent-2:#ffa8a7` (the 🐭 ears) drives the primary button and share chip (ink text, 4.5:1). The board frame is lavender `#d6d4ef`; the Size input and Solved chip are pale pink `#ffdcdb`, the solved count dark rose `#b83b45`. Dusk indigo `#4b4f9e` takes the clue numbers, and the landing-tile `<h2>` (amber doesn't read on white). Empty squares are white; ✕ notes are pale lavender `#e4e2f5`; rats show 🐭 on a very light pink `#ffecec` and aren't tappable. A cat's square (`.perch`) is a near-white warm `#fff8e8`, no ring; touching cats turn 😾 and a cat with no rat beside it turns 🙀, both with a red `#e5484d` ring; and an over-full row/column number goes red. The page gradient runs cream → pale lavender `#ecebf8`; the overlay scrim is a dark amber `rgba(85,60,25,.4)`. Representative emoji / favicon / spinner is 🐭; the counter is 🐱 placed/total.

## Persistence

`localStorage` key `kattenratten_v1`: best win time per board size + solved count — never the puzzle.

## Self-test

`runSelfTest()` regenerates every size `5`–`12`, asserts the generator's cats pass `isSolved` and show no conflicts, that every rat is paired with its own side-adjacent cat, that the counts match the cats, and that re-solving from the bare board is complete with deduced cats equal to the generator's. Every size should print "logically solvable ✅ (k contradiction steps)".

Headless check (Node with a stubbed DOM):

```bash
node -e '
const fs=require("fs"), vm=require("vm");
const js=fs.readFileSync("kattenratten/index.html","utf8").match(/<script>([\s\S]*?)<\/script>/)[1];
const dummy=new Proxy(function(){},{get:(t,p)=>p==="length"?0:dummy,apply:()=>dummy,set:()=>true});
const box={console,Math,Date,JSON,Array,Set,Map,String,Object,window:dummy,document:dummy,
  location:{hostname:"localhost",hash:""},
  localStorage:{getItem:()=>null,setItem:()=>{}},requestAnimationFrame:()=>{},setInterval:()=>{},clearInterval:()=>{},setTimeout:()=>{}};
vm.createContext(box); vm.runInContext(js, box, {filename:"kattenratten.js"});'
```
