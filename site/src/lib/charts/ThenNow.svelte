<script lang="ts">
	import { scaleLinear, scaleLog } from 'd3';
	import { data, fit, fmt, type Game } from '#lib/data.ts';
	import { inview } from '#lib/inview.ts';
	import { openGame } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	const cmp = data.compare!;
	const thenLabel = cmp.snapshot.slice(0, 4);
	const nowLabel = data.meta.snapshot.slice(0, 4);

	let shiftKind = $state<'all' | 'category' | 'mechanic'>('all');
	const shifts = $derived(
		cmp.shifts.filter((s) => shiftKind === 'all' || s.kind === shiftKind).slice(0, 14)
	);

	let width = $state(600);
	let shown = $state(false);
	let hover = $state<number | null>(null);
	const rowH = 28;
	const labelW = $derived(Math.min(230, width * 0.4));
	const x = $derived(
		scaleLinear()
			.domain([0, Math.max(...cmp.shifts.map((s) => Math.max(s.then, s.now)))])
			.nice()
			.range([labelW + 10, width - 50])
	);
	const height = $derived(shifts.length * rowH + 30);

	// Movers: games present in both snapshots, by change in rank (log ratio so #2→#1 ≈ #200→#100).
	const both = data.games.filter(
		(g): g is Game & { then: { rank: number; rating: number } } => !!g.then
	);
	let moverDir = $state<'up' | 'down'>('up');
	const movers = $derived(
		[...both]
			.filter((g) => g.rank <= 500 || g.then.rank <= 500)
			.sort((a, b) =>
				moverDir === 'up'
					? Math.log(b.then.rank / b.rank) - Math.log(a.then.rank / a.rank)
					: Math.log(a.then.rank / a.rank) - Math.log(b.then.rank / b.rank)
			)
			.slice(0, 12)
	);
	let mw = $state(600);
	const mLabel = $derived(Math.min(230, mw * 0.4));
	const rx = $derived(
		scaleLog()
			.domain([1, 5000])
			.range([mw - 20, mLabel + 14])
	);
	const rankTicks = [1, 10, 100, 1000, 5000];

	const stats = [
		{ label: 'Median year published', v: cmp.stats.medianYear, f: (n: number) => `${n}` },
		{ label: 'Median number of ratings', v: cmp.stats.medianVotes, f: fmt.int },
		{ label: 'Average rating', v: cmp.stats.meanRating, f: fmt.r2 },
		{
			label: 'Average play time (min)',
			v: cmp.stats.meanTime,
			f: (n: number) => `${Math.round(n)}`
		},
		{ label: 'Average weight', v: cmp.stats.meanWeight, f: fmt.r2 }
	];
</script>

<div class="tiles">
	{#each stats as s (s.label)}
		<div class="tile">
			<div class="lbl">{s.label}</div>
			<div class="pair">
				<span class="old">{s.f(s.v[0])}</span>
				<span class="arrow" aria-hidden="true">→</span>
				<span class="new">{s.f(s.v[1])}</span>
			</div>
			<div class="yrs">{thenLabel} → {nowLabel}, top {fmt.int(cmp.top)}</div>
		</div>
	{/each}
</div>

<div class="cols">
	<div class="card" use:inview={() => (shown = true)}>
		<p class="chart-title">What got more (and less) common</p>
		<p class="chart-sub">Share of the top {fmt.int(cmp.top)} games with each trait</p>
		<div class="controls" role="group" aria-label="Trait type">
			{#each [['all', 'All'], ['mechanic', 'Mechanics'], ['category', 'Categories']] as [k, l] (k)}
				<button
					class="chip"
					aria-pressed={shiftKind === k}
					onclick={() => (shiftKind = k as typeof shiftKind)}>{l}</button
				>
			{/each}
		</div>
		<ul class="legend">
			<li><span class="swatch dot" style:background="var(--series-2)"></span>{thenLabel}</li>
			<li><span class="swatch dot" style:background="var(--series-1)"></span>{nowLabel}</li>
		</ul>
		<div class="chart" bind:clientWidth={width}>
			<svg
				{width}
				{height}
				role="img"
				aria-label="Dumbbell chart of trait share in {thenLabel} and {nowLabel}"
			>
				<g class="grid">
					{#each x.ticks(4) as t (t)}
						<line x1={x(t)} x2={x(t)} y1="0" y2={height - 26} />
					{/each}
				</g>
				{#each shifts as s, i (s.name + s.kind)}
					{@const cy = i * rowH + rowH / 2}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<g
						class="row"
						class:dim={hover !== null && hover !== i}
						onpointerenter={() => (hover = i)}
						onpointerleave={() => (hover = null)}
					>
						<rect class="hit" x="0" y={cy - rowH / 2} {width} height={rowH} />
						<text class="name" x={labelW} y={cy} dy="0.35em" text-anchor="end"
							><title>{s.name}</title>{fit(s.name, labelW - 4)}</text
						>
						<line
							class="bar"
							x1={x(s.then)}
							x2={shown ? x(s.now) : x(s.then)}
							y1={cy}
							y2={cy}
							style:transition-delay="{i * 40}ms"
						/>
						<circle cx={x(s.then)} {cy} r="5" class="then" />
						<circle
							cx={shown ? x(s.now) : x(s.then)}
							{cy}
							r="5"
							class="now"
							style:transition-delay="{i * 40}ms"
						/>
						<text
							class="delta"
							x={Math.max(x(s.then), x(s.now)) + 10}
							y={cy}
							dy="0.35em"
							class:shown
						>
							{s.now >= s.then ? '+' : '−'}{Math.abs((s.now - s.then) * 100).toFixed(1)} pts
						</text>
					</g>
				{/each}
				<g class="axis">
					{#each x.ticks(4) as t (t)}
						<text x={x(t)} y={height - 8} text-anchor="middle">{fmt.pct(t)}</text>
					{/each}
				</g>
			</svg>
			{#if hover !== null}
				{@const s = shifts[hover]}
				<Tooltip x={x(s.now)} y={hover * rowH + rowH / 2} {width}>
					<span class="t">{s.name}</span>
					<div class="row"><span>{thenLabel}</span><span class="v">{fmt.pct(s.then, 1)}</span></div>
					<div class="row"><span>{nowLabel}</span><span class="v">{fmt.pct(s.now, 1)}</span></div>
				</Tooltip>
			{/if}
		</div>
		<p class="foot">
			Only traits whose name is the same in both snapshots are compared. BGG renamed many mechanics
			in 2019, so some changes are vocabulary rather than design.
		</p>
	</div>

	<div class="card">
		<p class="chart-title">Biggest movers since {thenLabel}</p>
		<p class="chart-sub">Games in both snapshots, top 500 then or now</p>
		<div class="controls" role="group" aria-label="Direction">
			<button class="chip" aria-pressed={moverDir === 'up'} onclick={() => (moverDir = 'up')}
				>Climbers</button
			>
			<button class="chip" aria-pressed={moverDir === 'down'} onclick={() => (moverDir = 'down')}
				>Fallers</button
			>
		</div>
		<ul class="legend">
			<li>
				<span class="swatch dot" style:background="var(--series-2)"></span>Rank in {thenLabel}
			</li>
			<li><span class="swatch dot" style:background="var(--series-1)"></span>Rank in {nowLabel}</li>
		</ul>
		<div bind:clientWidth={mw}>
			<svg
				width={mw}
				height={movers.length * rowH + 30}
				role="group"
				aria-label="Rank change for the biggest movers"
			>
				<g class="grid">
					{#each rankTicks as t (t)}
						<line x1={rx(t)} x2={rx(t)} y1="0" y2={movers.length * rowH} />
					{/each}
				</g>
				{#each movers as g, i (g.id)}
					{@const cy = i * rowH + rowH / 2}
					<g
						class="mrow"
						role="button"
						tabindex="0"
						aria-describedby="mv-{g.id}"
						onclick={() => openGame(g.id)}
						onkeydown={(e) => e.key === 'Enter' && openGame(g.id)}
					>
						<rect class="hit" x="0" y={cy - rowH / 2} width={mw} height={rowH} />
						<text class="name" x={mLabel} y={cy} dy="0.35em" text-anchor="end"
							>{fit(g.name, mLabel - 4)}</text
						>
						<line class="bar" x1={rx(g.then.rank)} x2={rx(g.rank)} y1={cy} y2={cy} />
						<circle cx={rx(g.then.rank)} {cy} r="5" class="then" />
						<circle cx={rx(g.rank)} {cy} r="5" class="now" />
					</g>
				{/each}
				<g class="axis">
					{#each rankTicks as t (t)}
						<text x={rx(t)} y={movers.length * rowH + 20} text-anchor="middle">#{fmt.int(t)}</text>
					{/each}
				</g>
			</svg>
			<div class="visually-hidden">
				{#each movers as g (g.id)}
					<span id="mv-{g.id}">Rank #{g.then.rank} in {thenLabel}, #{g.rank} in {nowLabel}</span>
				{/each}
			</div>
		</div>
		<p class="foot">Rank axis is logarithmic; better ranks to the right.</p>
	</div>
</div>

<style>
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}
	.tile {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.8rem 1rem;
	}
	.lbl {
		font-size: 0.8rem;
		color: var(--text-secondary);
	}
	.pair {
		display: flex;
		white-space: nowrap;
		align-items: baseline;
		gap: 0.4rem;
		margin: 0.15rem 0;
	}
	.old {
		font-size: 1.05rem;
		color: var(--text-muted);
	}
	.arrow {
		color: var(--text-muted);
	}
	.new {
		font-size: 1.6rem;
		font-weight: 650;
		color: var(--text-primary);
	}
	.yrs {
		font-size: 0.72rem;
		color: var(--text-muted);
	}
	.cols {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.25rem;
	}
	@media (max-width: 900px) {
		.cols {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.controls {
		display: flex;
		gap: 0.35rem;
		margin-bottom: 0.6rem;
		flex-wrap: wrap;
	}
	.chart {
		position: relative;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.hit {
		fill: transparent;
	}
	.row,
	.mrow {
		transition: opacity 0.2s;
	}
	.mrow {
		cursor: pointer;
		outline: none;
	}
	.mrow:hover .name,
	.mrow:focus-visible .name {
		fill: var(--text-primary);
	}
	.mrow:focus-visible .hit {
		fill: var(--surface-2);
		stroke: var(--series-1);
		stroke-width: 2px;
	}
	.row.dim {
		opacity: 0.35;
	}
	.name {
		fill: var(--text-secondary);
		font-size: 12.5px;
	}
	.bar {
		stroke: var(--axis);
		stroke-width: 2;
		transition: x2 0.9s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.then {
		fill: var(--series-2);
		stroke: var(--surface-1);
		stroke-width: 2;
	}
	.now {
		fill: var(--series-1);
		stroke: var(--surface-1);
		stroke-width: 2;
		transition: cx 0.9s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.delta {
		fill: var(--text-muted);
		font-size: 11px;
		font-variant-numeric: tabular-nums;
		opacity: 0;
		transition: opacity 0.4s 0.9s;
	}
	.delta.shown {
		opacity: 1;
	}
	.foot {
		font-size: 0.78rem;
		color: var(--text-muted);
		margin: 0.5rem 0 0;
	}
</style>
