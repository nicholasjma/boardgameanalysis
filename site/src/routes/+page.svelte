<script lang="ts">
	import { data, fmt } from '#lib/data.ts';
	import RatingDots from '#lib/charts/RatingDots.svelte';
	import Importance from '#lib/charts/Importance.svelte';
	import Beeswarm from '#lib/charts/Beeswarm.svelte';
	import Dependence from '#lib/charts/Dependence.svelte';
	import PredVsActual from '#lib/charts/PredVsActual.svelte';
	import MagicBars from '#lib/charts/MagicBars.svelte';
	import RankMagic from '#lib/charts/RankMagic.svelte';
	import TraitExplorer from '#lib/charts/TraitExplorer.svelte';
	import GameMap from '#lib/charts/GameMap.svelte';
	import ThenNow from '#lib/charts/ThenNow.svelte';
	import Waterfall from '#lib/charts/Waterfall.svelte';
	import StatTile from '#lib/components/StatTile.svelte';
	import GameDrawer from '#lib/components/GameDrawer.svelte';
	import GameSearch from '#lib/components/GameSearch.svelte';
	import GameTable from '#lib/components/GameTable.svelte';
	import ThemeToggle from '#lib/components/ThemeToggle.svelte';
	import { openGame } from '#lib/state.svelte.ts';

	const { meta, compare } = data;
	const top = data.games[0];
	const topMagic = [...data.games]
		.filter((g) => g.rank <= 100)
		.sort((a, b) => b.magic - a.magic)[0];
	const snapshotDate = new Date(`${meta.snapshot}-01`).toLocaleDateString('en-US', {
		month: 'long',
		year: 'numeric',
		timeZone: 'UTC'
	});
	const yearsTop = data.importance.findIndex((i) => i.feature === 'Year published') + 1;
	const sections = [
		['recipe', 'The recipe'],
		['prediction', 'Predicted vs actual'],
		['magic', 'Magic sauce'],
		['traits', 'Trait explorer'],
		['map', 'Game map'],
		['change', 'Since 2018'],
		['games', 'All games']
	] as const;
</script>

<svelte:head>
	<title>What's in a BoardGameGeek rating?</title>
	<meta
		name="description"
		content="An interactive analysis of what predicts BoardGameGeek ratings for the top {meta.games} board games."
	/>
</svelte:head>

<header class="top">
	<div class="inner">
		<a class="brand" href="#top">What’s in a <b>BGG</b> rating?</a>
		<nav aria-label="Sections">
			{#each sections as [id, label] (id)}
				<a href="#{id}">{label}</a>
			{/each}
		</nav>
		<div class="tools">
			<GameSearch />
			<ThemeToggle />
		</div>
	</div>
</header>

<main id="top">
	<section class="hero">
		<div class="wide">
			<p class="eyebrow">BoardGameGeek top {fmt.int(meta.games)} · {snapshotDate}</p>
			<h1>What’s in a rating?</h1>
			<p class="lede">
				Every dot below is one of the {fmt.int(meta.games)} highest-ranked board games on BoardGameGeek,
				placed by its average rating. We trained a model to guess each rating from nothing but
				<strong>when the game came out, how long it takes, and its categories and mechanics</strong>
				— then looked at what it gets right, and what it can’t explain.
			</p>
			<RatingDots />
			<div class="stats">
				<StatTile label="Games analyzed" value={meta.games} note="ranked, with 500+ ratings" />
				<StatTile
					label="Features the model sees"
					value={meta.features}
					note="{meta.mechanics} mechanics · {meta.categories} categories · year · time"
				/>
				<StatTile
					label="Variance explained"
					value={meta.r2 * 100}
					format={(n) => `${Math.round(n)}%`}
					note="out-of-sample, 5-fold cross-validation"
				/>
				<StatTile
					label="Typical error"
					value={meta.rmse}
					format={(n) => `±${n.toFixed(2)}`}
					note="RMSE in rating points (vs ±{fmt.r2(meta.baselineStd)} guessing the mean)"
				/>
			</div>
		</div>
	</section>

	<section id="recipe" class="block">
		<div class="wide">
			<p class="eyebrow">01 · The recipe</p>
			<h2>Newer and longer wins — then the details</h2>
			<div class="prose">
				<p>
					The model uses SHAP values to say how much each feature pushed a game’s predicted rating
					up or down. Averaged across games, <strong>year published</strong> is the #{yearsTop} driver
					and
					<strong>play time</strong> right behind it: BGG’s top games skew recent and long. After those,
					a handful of mechanics — solo modes, campaigns, variable player powers — carry most of the signal.
				</p>
			</div>
			<div class="grid-2">
				<div class="card">
					<p class="chart-title">Average influence on predicted rating</p>
					<p class="chart-sub">Mean absolute SHAP value, in rating points</p>
					<Importance />
				</div>
				<div class="card">
					<p class="chart-title">Direction of each effect</p>
					<p class="chart-sub">
						Each dot is a game; position is how much that feature moved its prediction
					</p>
					<Beeswarm />
				</div>
			</div>
			<div class="grid-2 tight">
				<div class="card">
					<Dependence feature="years_since_base" title="Effect of year published" binSize={2} />
				</div>
				<div class="card">
					<Dependence
						feature="avg_time"
						title="Effect of play time"
						unit=" min"
						binSize={20}
						clampMax={300}
					/>
				</div>
			</div>
		</div>
	</section>

	<section id="prediction" class="block">
		<div class="wide">
			<p class="eyebrow">02 · Predicted vs actual</p>
			<h2>Traits get you most of the way</h2>
			<div class="prose">
				<p>
					Each game’s prediction comes from a model that never saw it (five-fold cross-validation).
					Games above the diagonal are rated higher than their traits suggest. The typical miss is
					<strong>±{fmt.r2(meta.rmse)}</strong> points; the spread of ratings themselves is ±{fmt.r2(
						meta.baselineStd
					)}.
				</p>
			</div>
			<div class="card"><PredVsActual /></div>
		</div>
	</section>

	<section id="magic" class="block">
		<div class="wide">
			<p class="eyebrow">03 · Magic sauce</p>
			<h2>What the traits can’t explain</h2>
			<div class="grid-2 equation">
				<div class="prose">
					<p>
						Call the gap between a game’s actual and predicted rating its <strong
							>magic sauce</strong
						>: the part of its reputation that comes from execution — art, balance, theme, the way
						it plays — rather than its spec sheet.
					</p>
					<div class="eq" aria-label="Actual rating equals predicted rating plus magic sauce">
						<span class="term"
							><span class="tv">{fmt.r2(top.rating)}</span><span class="tl">actual</span></span
						>
						<span class="op">=</span>
						<span class="term"
							><span class="tv">{fmt.r2(top.pred)}</span><span class="tl">predicted</span></span
						>
						<span class="op">+</span>
						<span class="term magic"
							><span class="tv">{fmt.signed(top.magic)}</span><span class="tl">magic sauce</span
							></span
						>
					</div>
					<p>
						That’s <button class="inline" onclick={() => openGame(top.id)}>{top.name}</button>,
						BGG’s #1. In the top 100, the most magic belongs to
						<button class="inline" onclick={() => openGame(topMagic.id)}>{topMagic.name}</button>
						({fmt.signed(topMagic.magic)}).
					</p>
				</div>
				<div class="card">
					<p class="chart-title">How {top.name}’s rating is built</p>
					<p class="chart-sub">Starting from the typical game, feature by feature</p>
					<Waterfall game={top} />
				</div>
			</div>
			<div class="grid-2">
				<div class="card">
					<p class="chart-title">Most and least magic</p>
					<p class="chart-sub">Actual minus predicted rating</p>
					<MagicBars />
				</div>
				<div class="card">
					<p class="chart-title">The best-ranked games have the most magic</p>
					<p class="chart-sub">
						Rank is driven by rating, so this is partly by construction — but the size of the gap is
						the story: top-100 games beat their traits by well over half a point.
					</p>
					<RankMagic />
				</div>
			</div>
		</div>
	</section>

	<section id="traits" class="block">
		<div class="wide">
			<p class="eyebrow">04 · Trait explorer</p>
			<h2>Pick a mechanic or category</h2>
			<div class="prose">
				<p>
					See how games with a trait are rated compared with everything else, how much the model
					credits that trait, and which games carry it best.
				</p>
			</div>
			<TraitExplorer />
		</div>
	</section>

	<section id="map" class="block">
		<div class="wide">
			<p class="eyebrow">05 · Game map</p>
			<h2>The top 500, grouped by what they share</h2>
			<div class="prose">
				<p>
					Hierarchical clustering (Ward linkage) on shared categories and mechanics splits the top
					500 into
					{data.clusters.length} families, each named by the traits most over-represented in it. Every
					bubble is a game. Hover a family to light it up; click a bubble to open the game.
				</p>
			</div>
			<GameMap />
		</div>
	</section>

	{#if compare}
		<section id="change" class="block">
			<div class="wide">
				<p class="eyebrow">06 · Since 2018</p>
				<h2>Seven years of the BGG top {fmt.int(compare.top)}</h2>
				<div class="prose">
					<p>
						Comparing with a June 2018 snapshot: only <strong>{fmt.int(compare.retained)}</strong>
						of today’s top
						{fmt.int(compare.top)} were there in 2018, and
						<strong>{fmt.int(compare.newSince)}</strong> were published after it. The list got newer,
						shorter to play, better rated — and far more voted on.
					</p>
				</div>
				<ThenNow />
			</div>
		</section>
	{/if}

	<section id="games" class="block">
		<div class="wide">
			<p class="eyebrow">07 · All games</p>
			<h2>Every game, every number</h2>
			<div class="card"><GameTable /></div>
		</div>
	</section>

	<section class="block methods">
		<div class="wide grid-2">
			<div class="prose">
				<h3>Method</h3>
				<p>
					Games ranked in the BGG top {fmt.int(meta.games)} with more than 500 ratings. Features: years
					since
					{meta.baseYear} (older games count as {meta.baseYear}), play time capped at 300 minutes,
					and one-hot categories and mechanics that appear in at least 20 games. An XGBoost
					regressor (60 trees, depth 6) predicts average rating; all predictions are out-of-fold
					from 5-fold cross-validation (fold RMSE
					{meta.foldRmse.map((v) => v.toFixed(3)).join(', ')}). SHAP values are XGBoost’s exact
					TreeSHAP.
				</p>
				<p>
					Based on the 2018 analysis
					<a href="https://medium.com/@SoporificVacuum/whats-in-a-bgg-rating-5b769d53e2ac"
						>“What’s in a BGG rating?”</a
					>.
				</p>
			</div>
			<div class="prose">
				<h3>Data</h3>
				<p>
					{snapshotDate} data from
					<a href="https://www.kaggle.com/datasets/chik0di/board-games-dataset-complete-features"
						>Board Games Dataset Complete Features</a
					>
					by Chik0di (Open Database License), scraped from BoardGameGeek. The 2018 comparison uses a June
					2018 BGG snapshot. Board game data © BoardGameGeek and its contributors.
				</p>
				<p>
					Code: <a href="https://github.com/nicholasjma/boardgameanalysis"
						>github.com/nicholasjma/boardgameanalysis</a
					>
					· v{meta.version} · built {meta.generated.slice(0, 10)}
				</p>
			</div>
		</div>
	</section>
</main>

<GameDrawer />

<style>
	.top {
		position: sticky;
		top: 0;
		z-index: 20;
		background: color-mix(in srgb, var(--page) 85%, transparent);
		backdrop-filter: blur(10px);
		border-bottom: 1px solid var(--border);
	}
	.inner {
		max-width: var(--wide);
		margin: 0 auto;
		padding: 0.6rem 1.25rem;
		display: flex;
		align-items: center;
		gap: 1.25rem;
	}
	.brand {
		color: var(--text-primary);
		text-decoration: none;
		font-weight: 500;
		white-space: nowrap;
	}
	nav {
		display: flex;
		gap: 1rem;
		overflow-x: auto;
		flex: 1;
		scrollbar-width: none;
	}
	nav a {
		color: var(--text-secondary);
		text-decoration: none;
		font-size: 0.85rem;
		white-space: nowrap;
	}
	nav a:hover {
		color: var(--text-primary);
	}
	.tools {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		margin-left: auto;
	}
	@media (max-width: 900px) {
		nav {
			display: none;
		}
	}
	@media (max-width: 520px) {
		.brand {
			display: none;
		}
	}
	.wide {
		max-width: var(--wide);
		margin: 0 auto;
		padding: 0 1.25rem;
	}
	.hero {
		padding: 3.5rem 0 2rem;
	}
	h1 {
		font-size: clamp(2.6rem, 7vw, 4.75rem);
		font-weight: 750;
		letter-spacing: -0.035em;
		margin-bottom: 1rem;
	}
	.lede {
		font-size: 1.15rem;
		max-width: 62ch;
		margin-bottom: 2rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 0.75rem;
		margin-top: 2rem;
	}
	.block {
		padding: 4rem 0 1rem;
		scroll-margin-top: 3rem;
	}
	.grid-2 {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.25rem;
		margin-top: 1.25rem;
	}
	.grid-2.tight {
		margin-top: 1.25rem;
	}
	@media (max-width: 900px) {
		.grid-2 {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.equation {
		align-items: center;
	}
	.eq {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.9rem;
		margin: 1.5rem 0;
	}
	.term {
		display: grid;
		justify-items: center;
	}
	.tv {
		font-size: 2.6rem;
		font-weight: 700;
		letter-spacing: -0.03em;
		color: var(--text-primary);
		line-height: 1;
	}
	.magic .tv {
		color: var(--div-pos);
	}
	.tl {
		font-size: 0.78rem;
		color: var(--text-muted);
		margin-top: 0.3rem;
	}
	.op {
		font-size: 2rem;
		color: var(--text-muted);
		font-weight: 300;
	}
	.inline {
		background: none;
		border: 0;
		padding: 0;
		color: var(--series-1);
		text-decoration: underline;
		text-underline-offset: 3px;
		cursor: pointer;
		font: inherit;
	}
	.methods {
		padding-bottom: 4rem;
		border-top: 1px solid var(--grid);
		margin-top: 4rem;
	}
	.methods p {
		font-size: 0.9rem;
	}
</style>
