# What's in a BoardGameGeek rating?

An analysis of what predicts BoardGameGeek ratings: an XGBoost model that guesses each top
game's average rating from only its year, play time, categories and mechanics, plus an
interactive site that explains the results.

**Site:** https://nicholasjma.github.io/boardgameanalysis/ · **Original article (2018):**
[What's in a BGG rating?](https://medium.com/@SoporificVacuum/whats-in-a-bgg-rating-5b769d53e2ac)

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
```

Python dependencies are declared as compatible ranges in `pyproject.toml` and pinned exactly in
`uv.lock`; site dependencies are pinned exactly in `site/package.json` and `package-lock.json`.

CI (`.github/workflows/ci.yml`) runs lint, types and tests on Python 3.11–3.13 and builds the site.
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
