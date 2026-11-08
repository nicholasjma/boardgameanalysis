# What's in a BoardGameGeek rating?

An analysis of what predicts BoardGameGeek ratings: an XGBoost model that guesses each top
game's average rating from only its year, play time, categories and mechanics, plus an
interactive site that explains the results.

**Site:** https://nicholasjma.github.io/boardgameanalysis/ · **Original article (2018):**
[What's in a BGG rating?](https://medium.com/@SoporificVacuum/whats-in-a-bgg-rating-5b769d53e2ac)

## The site

The 3D map of the top 1,000 games is the home screen; everything else opens over it.

- **Fly it**: <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> to move, <kbd>Q</kbd>/<kbd>E</kbd>
  down and up, arrows or drag to look, scroll or pinch to zoom, <kbd>[</kbd>/<kbd>]</kbd> to step
  through the ranking. Click a game (or its label) to fly to it and list its most similar games.
- **Semantic zoom**: far out, the map names its regions (k-means on the embedding, named by their
  most over-represented traits); closer, game names; up close, cards with rank, year and rating;
  closest, the traits each game is built from.
- **Semantic scroll**: the guided tour is a story told in the side panel. Scrolling it, or
  scrolling over the map while it runs, flies the camera and recolours the map step by step.
- **Chapters**: the analysis (recipe, predicted vs actual, magic sauce, trait explorer, families,
  2018 comparison, all games, methods) opens as panes over the map, with their own URLs
  (`#recipe`) and back-button support. Any game anywhere links back to its place on the map.
- **⌘K / Ctrl+K**: jump to any game, chapter or trait. Enter flies to a game or lights up a trait
  on the map; Shift+Enter opens its details.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Node 22+.

```bash
uv sync                                   # Python 3.11+ env from uv.lock
uv run boardgameanalysis analyze          # model + static figures into output/
uv run boardgameanalysis export           # site/src/lib/data/analysis.json
cd site && npm ci && npm run dev          # http://localhost:5173
```

## Commands

| Command | What it does |
| --- | --- |
| `boardgameanalysis analyze [games.csv]` | Cross-validated model, SHAP, clustering; writes PNGs, `magic.csv`, `predictions.csv`, `clusters.html` to `output/` |
| `boardgameanalysis export [games.csv] --compare old.csv` | Writes the JSON document the site is built from |
| `boardgameanalysis import-kaggle <csv>` | Converts the Kaggle dataset below into this project's CSV schema |
| `boardgameanalysis fetch --ranks boardgames_ranks.csv` | Pulls live data from the BGG XML API (needs a token; see below) |

## Data

| File | Snapshot | Source |
| --- | --- | --- |
| `data/bgg_kaggle_2509.csv` | Sept 2025, top 2,000 | [Board Games Dataset Complete Features](https://www.kaggle.com/datasets/chik0di/board-games-dataset-complete-features) by Chik0di, [ODbL](https://opendatacommons.org/licenses/odbl/1-0/); converted with `import-kaggle` |
| `data/bgg_db_1806.csv` | June 2018, top 5,000 | The original 2018 analysis |

Board game data © BoardGameGeek and its contributors.

### Live data from BGG

BGG's XML API requires a registered application token
([apply here](https://boardgamegeek.com/using_the_xml_api)). Once you have one:

1. Download `boardgames_ranks.csv` (or the zip) from
   [boardgamegeek.com/data_dumps/bg_ranks](https://boardgamegeek.com/data_dumps/bg_ranks) while logged in.
2. Fetch details for the top N games. Requests are rate-limited to one every 5 seconds (BGG's
   crawl delay), batched 20 IDs at a time, retried with backoff, and cached in
   `data/cache/games.jsonl` so an interrupted run resumes:

   ```bash
   export BGG_TOKEN=...
   uv run boardgameanalysis fetch --ranks boardgames_ranks.csv --top 2000 --out data/games.csv
   uv run boardgameanalysis export data/games.csv --snapshot 2026-11
   ```

## Model

- Ranked games in the top 5,000 with more than 500 ratings.
- Features: years since 2000 (older games clamp to 0), play time capped at 300 min, one-hot
  categories and mechanics seen in at least 20 games.
- `XGBRegressor(n_estimators=60, max_depth=6, learning_rate=0.1, colsample_bytree=0.3, reg_alpha=10)`,
  evaluated with shuffled 5-fold CV. All site predictions are out-of-fold.
- SHAP values come from XGBoost's native TreeSHAP (`pred_contribs`), so each game's waterfall
  sums exactly to its prediction.
- "Magic sauce" = actual rating − predicted rating.
- Families: Ward hierarchical clustering on the top 500 games' trait vectors.
- 3D game space: UMAP (Jaccard distance, 15 neighbours) on the top 1,000 games' trait vectors.

## Development

```bash
uv run ruff check && uv run ruff format --check   # lint + format
uv run mypy                                        # strict type checking
uv run pytest                                      # tests
uv run pre-commit install                          # run the above on commit

cd site
npm run lint      # prettier + eslint
npm run check     # svelte-check / TypeScript
npm run build     # static build into site/build
npm test          # Playwright: axe, contrast and keyboard tests (after build;
                  # first run: npx playwright install chromium)
```

Python dependencies are declared as compatible ranges in `pyproject.toml` and pinned exactly in
`uv.lock`; site dependencies are pinned exactly in `site/package.json` and `package-lock.json`.

CI (`.github/workflows/ci.yml`) runs lint, types and tests on Python 3.11–3.13, builds the site,
and runs the accessibility suite.

## Accessibility

The site targets WCAG 2.2 AA, and `site/tests/` checks it on every push, in light and dark themes,
at desktop and phone sizes:

- **axe-core** scan of the map, every chapter pane, the guided tour, and the command palette and
  game drawer while open.
- **Text contrast** of every visible text run, including SVG chart labels (which axe skips),
  composited over its real background; and the colour tokens themselves against each surface.
- **Keyboard**: skip link, ⌘K / Ctrl+K and `/` open the command palette, focus is trapped in
  dialogs and returned on close, and every control shows a visible focus indicator.

Every chart has a table view and honours `prefers-reduced-motion`; the 3D map can be flown,
searched and stepped through entirely from the keyboard, and its panel lists every game.
`pages.yml` regenerates the data and deploys the site to GitHub Pages on every push to `master`.

## Layout

```
src/boardgameanalysis/   Python package
  api.py                   BGG XML API client (rate limiting, retries)
  dataset.py               loaders: BGG fetch cache, Kaggle, 2018 CSV, rank dumps
  features.py              filtering and one-hot trait features
  model.py                 cross-validated XGBoost + SHAP
  clustering.py            Ward clustering and t-SNE
  embedding.py             3D UMAP for the site's game space
  plots.py                 static matplotlib/plotly figures
  export.py                JSON for the site
  cli.py                   `boardgameanalysis` command
site/                    SvelteKit + D3 static site
tests/                   pytest suite
legacy/                  the original 2018 notebook and figures
```
