# Kattenspellen

Cat-themed browser puzzle games. Each game is a self-contained riff on a classic logic puzzle, dressed in cats and a shared pastel look. The landing page (`index.html`) tiles the games; each game lives in `<game>/index.html`.

Games:

- **Catoku** (`catoku/`) — a "Queens"-style puzzle. See `catoku/CLAUDE.md`.
- **Catwalk** (`catwalk/`) — a "Train Tracks"-style puzzle. See `catwalk/CLAUDE.md`.
- **Meowsweeper** (`meowsweeper/`) — a "Minesweeper"-style puzzle. See `meowsweeper/CLAUDE.md`.
- **Purrlink** (`purrlink/`) — a "Numberlink"-style puzzle. See `purrlink/CLAUDE.md`.

Every game is built to the shared criteria below, so each is solid on its own and obviously part of the same family. Conventions that are strictly one game's live in that game's own `<game>/CLAUDE.md`.

## Delivery & footprint

- **One file per game**: `<game>/index.html` — `<style>`, HTML, one `<script>`. No framework, no dependencies, no build step.
- **Client-side only.** Works opened from disk or a static server; no runtime network calls.
- **No ads, no telemetry, no tracking.** It's stated in the page copy/meta — keep it true.

## Persistence

`localStorage` only, one namespaced + versioned key per game (e.g. `catoku_v1`). Store outcomes and stats (best time, solved count), never restorable game state — the puzzle must not be recoverable from storage.

## Game modes

Every game offers the same two modes:

- **Daily challenge** — one instance per day, shared by everyone (seeded on the date). Win state persists so a solved day reads as done.
- **New game** — spin up unlimited fresh instances on demand, each with a **selectable difficulty**. What the difficulty knob is depends on the game (Catoku uses board size); a game defines its own and documents it in its `CLAUDE.md`.

## Challenge links

Every game lets a player share the exact board they're on. A 🔗 chip next to the counter is always shown; on win, a **Copy challenge** button on the win overlay does the same. The link's **hash** carries only `N` and the seed string (URL-encoded), plus — once solved — the challenger's time in seconds, `~`-separated: `…/<game>/#c=<N>~<seed>[~<seconds>]`. The link never carries the solution — the receiver re-runs the generator from the seed, so the same seed reproduces the same board anywhere (determinism is what makes this work). On load, a valid hash loads that board: with a time it shows a "Beat <time>" banner and the clock tints green/red against the target; without one it shows a "Shared board" banner and no target. An **invalid or out-of-range** hash declines with a short notice and falls back to the daily board — never fabricate a board. Times are self-reported and unverified (fine for a friendly race); no version pinning. Same encode/parse/validate helpers in every game — keep them identical.

## Determinism & fairness

For any game with generated content:

- **Seeded RNG.** Thread a seeded `rng` through generation. Never call `Math.random()` or `Date.now()` inside generation; `Math.random()` is fine for cosmetic-only choices (e.g. which cat emoji renders).
- **Daily instance** keyed on the date (`"YYYY-MM-DD|…"`), identical for everyone that day; **fresh instances** from a distinct seed pattern.
- **Logically solvable — the hard invariant.** Every served instance must be solvable by pure logical deduction — at every point the next move can be *proven*. Proof by contradiction counts as deduction: assume one move, play out its forced consequences under the direct rules, and if the board breaks, the opposite is proven. Keep it to one level (the consequences of an assumption use direct rules only, never a nested assumption); search and trial-and-error over branches are out. Generation must *prove* it with a deductive solver (human-style inference under the same rules the player plays) before serving — never assume it. An instance that isn't fully deducible is a bug, not a hard puzzle; regenerate or fail loudly rather than serve it.
- **Say what it is, not what it isn't.** UI copy, meta, comments and docs describe fairness positively — "solvable by logic", "fully deducible". No negated taglines tacked on.
- **Prove from the player's actual starting state.** The deductive proof must begin from the exact state the player is handed — if the solver assumes an opening is already revealed, the served board must pre-reveal it too, or the player who deviates isn't playing the puzzle we proved. Relatedly, the first interaction must never be an unavoidable loss (e.g. Meowsweeper pre-reveals the safe opening region so the first dig can't hit a monster).

## One source of truth for rules

A game's rules are usually encoded in several functions (generator, solver, validator, conflict check). Every encoding must agree. Enumerate them and change a rule in all of them, or they disagree.

## Self-test

- Ship a `runSelfTest()` that logs to the console on `localhost` or when the URL ends in `#selftest`, asserting the game's invariants (valid state + fairness/solvability) across its range of configs.
- The `<script>` must load headless in Node with a stubbed DOM (no top-level DOM assumptions that break outside a browser). Each game documents its exact headless command in its own `CLAUDE.md`.

## Discoverability

Every page carries the full head set: `<title>`, `<meta name="description">`, canonical URL, Open Graph tags (type/title/description/url/image), Twitter Card tags (`twitter:card` + `twitter:image` — `summary_large_image` for games, `summary` for the landing; title/description fall back to OG so links unfurl with an image in messaging apps and on X), `theme-color`, the inline-SVG emoji favicon, `apple-touch-icon`, and a per-game `manifest.webmanifest`. Add each game to the repo `sitemap.xml`.

Each game also ships two shared social/README assets under `assets/`: a `<game>-preview.png` (700×700, the og/twitter image — a clean single frame of the game) and a `<game>-demo.gif` (linked in `README.md` at `width="400"`).

## Visual style

The look is shared so the games read as one family; a per-game palette makes each one distinct. Split accordingly.

**Family constants — never vary:**

- **Font**: `"Noto Color Emoji","Nunito","Segoe UI",system-ui,-apple-system,sans-serif`.
- **Emoji**: Google's Noto, identical on every device — `assets/noto-emoji.woff2` is Noto Color Emoji subset to the emoji the pages use (COLRv1 for Chrome/Firefox + OT-SVG for Safari in one file), first in the font stack. Added an emoji? Rerun `uv run assets/build-emoji-font.py`, or it renders as the device's native emoji.
- **Background**: a soft `linear-gradient(160deg, …)` from cream `#fdf6f0` to a pale tint of the game's accent. The cream start and the softness are fixed; the second stop is per-game (see below).
- **Neutrals**: `--ink:#5b4a52` (soft mauve text, not black), `--panel:#ffffff` (cards), `--shadow:0 6px 20px rgba(120,90,110,.15)`.
- **Shape**: generous rounding (cards ~20px, buttons/cells ~8–12px) and soft shadows.
- **Motion**: small, springy. Hover lifts (`translateY(-2px…-4px)`), press scales down, wins pop.
- **Component vocabulary**: pill tabs (`border-radius:999px`), rounded/pill buttons (the primary one filled with the game's accent), an `h1` + one-line subtitle header (above it, a round `.back` ← chip linking to `../index.html`), chips for clock/stats, and `.overlay` modals (rules/win/lose — a centered `.card` on the accent-tinted scrim, dismissable by clicking the backdrop). Reuse these; don't invent parallels.
- **Loading spinner**: `loadGame` adds `#board.busy`, then generates the board on the next frame (`setupGame`) so the browser gets to draw the spinner first. The spinner is the game's emoji spinning in a white disc and fades in after 150ms, so boards that load quickly never flash it. Cached boards skip it, and a newer load cancels a pending one. The wrapper and CSS are identical in every game except the emoji; keep them identical.
- **Landing tile**: one `a.card` per game — emoji + `<h2>` name + one-line description.
- **Mood**: soft, playful, pastel. Cats and emoji, never harsh.
- **Accessibility floor**: any glyph drawn on a colored region clears 3:1 contrast against every region color; region palettes keep all pairs distinct (ΔE ≥ 18) even when touching.
- **Responsive, mobile-first**: viewport-scaled sizing (`clamp`), touch-friendly (`touch-action`, no tap-highlight), works on small screens.
- **Naming**: each game's name is a cat pun.

**Per-game identity — vary exactly these:**

- **Signature palette**: the game picks its own `--accent` and `--accent-2`. `--accent` is the signature (in-game headings/highlights, `theme-color` meta; the landing-tile `<h2>` takes one of the game's hues, darkened as needed to read on white); `--accent-2` is a *distinct second hue* driving the primary button and other secondary highlights — so every game reads as a two-color scheme, never monochrome. The two accents may be complementary (Catoku pink `#f7a8c4` + blue `#3f8fd6`) or adjacent on the wheel (Catwalk green `#7cc47f` + teal `#2b9d9d`); either way the button is `--accent-2`, and a game's own tile art carries both hues (Catwalk's paw tiles are a light-teal tint with teal `--accent-2` trail bars). The landing page shares Catoku's scheme for now.
- **Background second stop**: the pale-accent end of the page gradient (Catoku lilac `#f5eefb`, Catwalk green `#e8f4e6`). Cream start stays fixed.
- **Overlay scrim**: the `.overlay` backdrop is a dark tint of the game's accent at ~.4 alpha (Catoku mauve `rgba(70,50,65,.4)`, Catwalk green `rgba(40,70,45,.4)`).
- **Representative emoji** (Catoku 🐱) — used in the tile and the favicon.
- **Name and one-line description.**
- **Game-specific region/glyph palette** (within the accessibility floor above).

## Code style

- Vanilla ES, `"use strict"`, 2-space indent, semicolons.
- Terse and compact: multiple statements per line are fine, short helper names, inline arrow helpers. Match the surrounding density.
- Section headers use `/* ---------- name ---------- */`.
- The `<script>` runs top-to-bottom in commented sections.

## Build, test, run

No build — open or serve `<game>/index.html`.

Run a static server, then hard-refresh (Ctrl+F5) to pick up changes:

```bash
python -m http.server 80    # http://localhost/
```

`runSelfTest()` runs on `localhost` or when the URL ends in `#selftest`. Each game documents its headless Node check (stubbed DOM) in its own `CLAUDE.md`.

## Deploy

`.github/workflows/deploy.yml` uploads the repo root to GitHub Pages when a release is published: `kattenspellen.github.io/games/` is the landing, `.../games/<game>/` is each game.
