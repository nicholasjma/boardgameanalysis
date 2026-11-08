<script lang="ts">
	import { bin, scaleLinear, max } from 'd3';
	import { data, fmt } from '#lib/data.ts';
	import { openGame, ui } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	const traitIndex = new Map(data.traitKeys.map((k, i) => [k, i]));
	const traits = [...data.traits].sort((a, b) => a.name.localeCompare(b.name));
	const quick = [...data.traits]
		.filter((t) => t.effect !== null)
		.sort((a, b) => b.importance - a.importance)
		.slice(0, 8);

	const trait = $derived(data.traits.find((t) => t.key === ui.trait) ?? data.traits[0]);
	const idx = $derived(traitIndex.get(trait.key) ?? 0);
	const members = $derived(data.games.filter((g) => g.traits.includes(idx)));
	const topMembers = $derived([...members].sort((a, b) => a.rank - b.rank).slice(0, 6));

	const all = data.games.map((g) => g.rating);
	const lo = Math.floor(Math.min(...all) * 4) / 4;
	const hi = Math.ceil(Math.max(...all) * 4) / 4;
	const binner = bin().domain([lo, hi]).thresholds(28);
	const allBins = binner(all);
	const traitBins = $derived(binner(members.map((g) => g.rating)));

	// Both series as share of their own group, so a niche trait is comparable to the whole.
	const allShare = allBins.map((b) => b.length / all.length);
	const traitShare = $derived(traitBins.map((b) => b.length / Math.max(1, members.length)));

	let width = $state(600);
	let hover = $state<number | null>(null);
	const height = 240;
	const m = { top: 10, right: 8, bottom: 34, left: 8 };
	const x = $derived(
		scaleLinear()
			.domain([lo, hi])
			.range([m.left, width - m.right])
	);
	const y = $derived(
		scaleLinear()
			.domain([0, Math.max(max(allShare) ?? 0, max(traitShare) ?? 0)])
			.range([height - m.bottom, m.top])
	);
	const meanAll = data.meta.meanRating;
	const meanTrait = $derived(
		members.reduce((a, g) => a + g.rating, 0) / Math.max(1, members.length)
	);

	function col(b: { x0?: number; x1?: number }, share: number) {
		const x0 = x(b.x0 ?? 0) + 1;
		const x1 = x(b.x1 ?? 0) - 1;
		const yTop = y(share);
		const yBase = y(0);
		const r = Math.min(4, (x1 - x0) / 2, Math.max(0, yBase - yTop));
		return `M${x0},${yBase} V${yTop + r} Q${x0},${yTop} ${x0 + r},${yTop} H${x1 - r} Q${x1},${yTop} ${x1},${yTop + r} V${yBase} Z`;
	}
</script>

<div class="explorer">
	<div class="controls">
		<label class="pick">
			<span class="visually-hidden">Choose a category or mechanic</span>
			<select bind:value={ui.trait}>
				<optgroup label="Mechanics">
					{#each traits.filter((t) => t.kind === 'mechanic') as t (t.key)}
						<option value={t.key}>{t.name} ({t.count})</option>
					{/each}
				</optgroup>
				<optgroup label="Categories">
					{#each traits.filter((t) => t.kind === 'category') as t (t.key)}
						<option value={t.key}>{t.name} ({t.count})</option>
					{/each}
				</optgroup>
			</select>
		</label>
		<div class="quick" role="group" aria-label="Most influential traits">
			{#each quick as t (t.key)}
				<button class="chip" aria-pressed={ui.trait === t.key} onclick={() => (ui.trait = t.key)}
					>{t.name}</button
				>
			{/each}
		</div>
	</div>

	<div class="grid2">
		<div class="card">
			<p class="chart-title">Rating distribution: {trait.name} vs all games</p>
			<ul class="legend">
				<li>
					<span class="swatch" style:background="var(--series-1)"></span>{trait.name} ({members.length})
				</li>
				<li>
					<span class="swatch" style:background="var(--neutral-dot)"></span>All {fmt.int(
						data.meta.games
					)} games
				</li>
			</ul>
			<div class="chart" bind:clientWidth={width}>
				<svg
					{width}
					{height}
					role="img"
					aria-label="Histogram of ratings for {trait.name} compared with all games"
				>
					{#each allBins as b, i (i)}
						<path d={col(b, allShare[i])} class="all" />
					{/each}
					{#each traitBins as b, i (i)}
						<!-- svelte-ignore a11y_no_static_element_interactions -->
						<path
							d={col(b, traitShare[i])}
							class="trait"
							class:hl={hover === i}
							onpointerenter={() => (hover = i)}
							onpointerleave={() => (hover = null)}
						/>
					{/each}
					<line
						class="mean all-m"
						x1={x(meanAll)}
						x2={x(meanAll)}
						y1={m.top}
						y2={height - m.bottom}
					/>
					<line
						class="mean trait-m"
						x1={x(meanTrait)}
						x2={x(meanTrait)}
						y1={m.top}
						y2={height - m.bottom}
					/>
					<g class="axis">
						{#each x.ticks(6) as t (t)}
							<text x={x(t)} y={height - m.bottom + 18} text-anchor="middle">{t.toFixed(1)}</text>
						{/each}
					</g>
					<text class="axis-title" x={width - m.right} y={height - 2} text-anchor="end"
						>Average rating →</text
					>
				</svg>
				{#if hover !== null}
					{@const b = traitBins[hover]}
					<Tooltip x={x(((b.x0 ?? 0) + (b.x1 ?? 0)) / 2)} y={y(traitShare[hover])} {width}>
						<span class="t">{(b.x0 ?? 0).toFixed(2)}–{(b.x1 ?? 0).toFixed(2)}</span>
						<div class="row">
							<span class="v">{fmt.pct(traitShare[hover], 1)}</span><span
								>of {trait.name} ({b.length})</span
							>
						</div>
						<div class="row">
							<span class="v">{fmt.pct(allShare[hover], 1)}</span><span>of all games</span>
						</div>
					</Tooltip>
				{/if}
			</div>
		</div>

		<div class="side">
			<div class="tiles">
				<div class="tile">
					<div class="lbl">Mean rating</div>
					<div class="big">{fmt.r2(meanTrait)}</div>
					<div class="delta" class:up={meanTrait >= meanAll}>
						{fmt.signed(meanTrait - meanAll)} vs all
					</div>
				</div>
				<div class="tile">
					<div class="lbl">Model effect when present</div>
					<div class="big">{trait.effect === null ? '—' : fmt.signed(trait.effect, 3)}</div>
					<div class="delta muted">holding year & time fixed</div>
				</div>
				<div class="tile">
					<div class="lbl">Avg magic sauce</div>
					<div class="big">{fmt.signed(trait.meanMagic)}</div>
					<div class="delta muted">what the traits don't explain</div>
				</div>
				<div class="tile">
					<div class="lbl">Avg weight</div>
					<div class="big">{trait.meanWeight === null ? '—' : fmt.r2(trait.meanWeight)}</div>
					<div class="delta muted">1 = light · 5 = heavy</div>
				</div>
			</div>
			<p class="chart-title">Highest-ranked {trait.name} games</p>
			<ol class="games">
				{#each topMembers as g (g.id)}
					<li>
						<button onclick={() => openGame(g.id)}>
							<span class="rk">#{g.rank}</span>
							<span class="nm">{g.name}</span>
							<span class="rt">{fmt.r2(g.rating)}</span>
						</button>
					</li>
				{/each}
			</ol>
		</div>
	</div>
	<p class="note">
		The “model effect” is the average SHAP contribution of this trait to games that have it — how
		much the model moves the prediction for that trait alone. It can differ from the raw difference
		in mean rating, which also absorbs year, length and other traits that travel with it.
	</p>
</div>

<style>
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	select {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.45rem 0.6rem;
		max-width: 320px;
	}
	.quick {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.grid2 {
		display: grid;
		grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
		gap: 1.25rem;
	}
	@media (max-width: 820px) {
		.grid2 {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.chart {
		position: relative;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.all {
		fill: var(--neutral-dot);
		opacity: 0.35;
		transition: d 0.5s;
	}
	.trait {
		fill: var(--series-1);
		opacity: 0.85;
		transition: d 0.6s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.trait.hl {
		opacity: 1;
		stroke: var(--text-primary);
		stroke-width: 1;
	}
	.mean {
		stroke-width: 1.5;
		transition:
			x1 0.6s,
			x2 0.6s;
	}
	.all-m {
		stroke: var(--text-muted);
	}
	.trait-m {
		stroke: var(--series-1);
	}
	.tiles {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.6rem;
		margin-bottom: 1rem;
	}
	.tile {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.7rem 0.8rem;
	}
	.lbl {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}
	.big {
		font-size: 1.5rem;
		font-weight: 650;
		color: var(--text-primary);
	}
	.delta {
		font-size: 0.75rem;
		color: var(--div-neg);
	}
	.delta.up {
		color: var(--good);
	}
	.delta.muted {
		color: var(--text-muted);
	}
	.games {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.games button {
		display: grid;
		grid-template-columns: 3.2rem 1fr auto;
		width: 100%;
		gap: 0.5rem;
		text-align: left;
		background: none;
		border: 0;
		border-bottom: 1px solid var(--grid);
		padding: 0.4rem 0.2rem;
		cursor: pointer;
		font-size: 0.88rem;
	}
	.games button:hover {
		background: var(--surface-2);
	}
	.rk,
	.rt {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.nm {
		color: var(--text-primary);
	}
	.note {
		font-size: 0.82rem;
		color: var(--text-muted);
		margin-top: 1rem;
		max-width: var(--measure);
	}
</style>
