# Kattenspellen

Cat-themed browser puzzle games. Each game is a self-contained riff on a
classic logic puzzle, dressed in cats and a shared pastel look. The landing
page (`index.html`) tiles the games; each game lives in `<game>/index.html`.

Games:

- **Catoku** (`catoku/`) — a "Queens"-style puzzle. See `catoku/CLAUDE.md`.
- **Catwalk** (`catwalk/`) — a "Train Tracks"-style puzzle. See `catwalk/CLAUDE.md`.

Every game is built to the shared criteria below, so each is solid on its own
and obviously part of the same family. Conventions that are strictly one game's
live in that game's own `<game>/CLAUDE.md`.

## Delivery & footprint

- **One file per game**: `<game>/index.html` — `<style>`, HTML, one `<script>`.
  No framework, no dependencies, no build step.
- **Client-side only.** Works opened from disk or a static server; no runtime
  network calls.
- **No ads, no telemetry, no tracking.** It's stated in the page copy/meta —
  keep it true.

## Persistence

`localStorage` only, one namespaced + versioned key per game (e.g.
`catoku_v1`). Store outcomes and stats (best time, solved count), never
restorable game state — the puzzle must not be recoverable from storage.

## Game modes

Every game offers the same two modes:

- **Daily challenge** — one instance per day, shared by everyone (seeded on the
  date). Win state persists so a solved day reads as done.
- **New game** — spin up unlimited fresh instances on demand, each with a
  **selectable difficulty**. What the difficulty knob is depends on the game
  (Catoku uses board size); a game defines its own and documents it in its
  `CLAUDE.md`.

## Determinism & fairness

For any game with generated content:

- **Seeded RNG.** Thread a seeded `rng` through generation. Never call
  `Math.random()` or `Date.now()` inside generation; `Math.random()` is fine
  for cosmetic-only choices (e.g. which cat emoji renders).
- **Daily instance** keyed on the date (`"YYYY-MM-DD|…"`), identical for
  everyone that day; **fresh instances** from a distinct seed pattern.
- **Logically solvable — the hard invariant.** Every served instance must be
  solvable by pure logical deduction, no guessing and no backtracking.
  Generation must *prove* it with a deductive solver (human-style inference
  under the same rules the player plays) before serving — never assume it. An
  instance that isn't fully deducible is a bug, not a hard puzzle; regenerate or
  fail loudly rather than serve it.

## One source of truth for rules

A game's rules are usually encoded in several functions (generator, solver,
validator, conflict check). Every encoding must agree. Enumerate them and
change a rule in all of them, or they disagree.

## Self-test

- Ship a `runSelfTest()` that logs to the console on `localhost` or when the
  URL ends in `#selftest`, asserting the game's invariants (valid state +
  fairness/solvability) across its range of configs.
- The `<script>` must load headless in Node with a stubbed DOM (no top-level
  DOM assumptions that break outside a browser). Each game documents its exact
  headless command in its own `CLAUDE.md`.

## Discoverability

Every page carries the full head set: `<title>`, `<meta name="description">`,
canonical URL, Open Graph tags (type/title/description/url/image),
`theme-color`, the inline-SVG emoji favicon, `apple-touch-icon`, and a per-game
`manifest.webmanifest`. Add each game to the repo `sitemap.xml`.

## Visual style

The look is shared so the games read as one family; a per-game palette makes
each one distinct. Split accordingly.

**Family constants — never vary:**

- **Font**: `"Nunito","Segoe UI",system-ui,-apple-system,sans-serif`.
- **Background**: a soft `linear-gradient(160deg, …)` from cream `#fdf6f0` to a
  pale tint of the game's accent. The cream start and the softness are fixed;
  the second stop is per-game (see below).
- **Neutrals**: `--ink:#5b4a52` (soft mauve text, not black),
  `--panel:#ffffff` (cards), `--shadow:0 6px 20px rgba(120,90,110,.15)`.
- **Shape**: generous rounding (cards ~20px, buttons/cells ~8–12px) and soft
  shadows.
- **Motion**: small, springy. Hover lifts (`translateY(-2px…-4px)`), press
  scales down, wins pop.
- **Component vocabulary**: pill tabs (`border-radius:999px`), rounded/pill
  buttons (the primary one filled with the game's accent), an `h1` + one-line
  subtitle header, chips for clock/stats. Reuse these; don't invent parallels.
- **Landing tile**: one `a.card` per game — emoji + `<h2>` name + one-line
  description.
- **Mood**: soft, playful, pastel. Cats and emoji, never harsh.
- **Accessibility floor**: any glyph drawn on a colored region clears 3:1
  contrast against every region color; region palettes keep all pairs distinct
  (ΔE ≥ 18) even when touching.
- **Responsive, mobile-first**: viewport-scaled sizing (`clamp`),
  touch-friendly (`touch-action`, no tap-highlight), works on small screens.
- **Naming**: each game's name is a cat pun.

**Per-game identity — vary exactly these:**

- **Signature palette**: the game picks its own `--accent` and `--accent-2`.
  `--accent` is the signature (in-game headings/highlights, landing-tile `<h2>`,
  `theme-color` meta); `--accent-2` is a *distinct second hue* driving the
  primary button and other secondary highlights — so every game reads as a
  two-color scheme, never monochrome. The two accents may be complementary
  (Catoku pink `#f7a8c4` + blue `#3f8fd6`) or adjacent on the wheel (Catwalk
  green `#7cc47f` + teal `#2b9d9d`); either way the button is `--accent-2`, and
  a game's own tile art carries both hues (Catwalk's paw tiles are a light-teal
  tint with teal `--accent-2` trail bars). The landing page shares Catoku's
  scheme for now.
- **Background second stop**: the pale-accent end of the page gradient (Catoku
  lilac `#f5eefb`, Catwalk green `#e8f4e6`). Cream start stays fixed.
- **Overlay scrim**: the `.overlay` backdrop is a dark tint of the game's accent
  at ~.4 alpha (Catoku mauve `rgba(70,50,65,.4)`, Catwalk green
  `rgba(40,70,45,.4)`).
- **Representative emoji** (Catoku 🐱) — used in the tile and the favicon.
- **Name and one-line description.**
- **Game-specific region/glyph palette** (within the accessibility floor above).

## Code style

- Vanilla ES, `"use strict"`, 2-space indent, semicolons.
- Terse and compact: multiple statements per line are fine, short helper names,
  inline arrow helpers. Match the surrounding density.
- Section headers use `/* ---------- name ---------- */`.
- The `<script>` runs top-to-bottom in commented sections.

## Build, test, run

No build — open or serve `<game>/index.html`.

Run a static server, then hard-refresh (Ctrl+F5) to pick up changes:

```bash
python -m http.server 80    # http://localhost/
```

`runSelfTest()` runs on `localhost` or when the URL ends in `#selftest`. Each
game documents its headless Node check (stubbed DOM) in its own `CLAUDE.md`.

## Deploy

`.github/workflows/deploy.yml` uploads the repo root to GitHub Pages when a
release is published: `kattenspellen.github.io/games/` is the landing,
`.../games/<game>/` is each game.
