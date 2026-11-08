<script lang="ts">
	import { scaleLinear, scaleLog, line, curveMonotoneX, mean } from 'd3';
	import { data, fmt, type Game } from '#lib/data.ts';
	import { inview } from '#lib/inview.ts';
	import { nearest, type Pt } from '#lib/nearest.ts';
	import { openGame } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	const games = data.games;
	const maxRank = Math.max(...games.map((g) => g.rank));
	let width = $state(700);
	let shown = $state(false);
	let hover = $state<Pt<Game> | null>(null);
	const height = 340;
	const m = { top: 16, right: 16, bottom: 40, left: 48 };

	// Log-spaced bins so the top 100 gets as much resolution as the long tail.
	const edges = [1, 11, 26, 51, 101, 201, 351, 501, 751, 1001, 1501, maxRank + 1];
	const binned = edges.slice(0, -1).map((e, i) => {
		const sel = games.filter((g) => g.rank >= e && g.rank < edges[i + 1]);
		return {
			x: Math.sqrt(e * (edges[i + 1] - 1)),
			y: mean(sel, (g) => g.magic) ?? 0,
			n: sel.length,
			lo: e,
			hi: edges[i + 1] - 1
		};
	});

	const x = $derived(
		scaleLog()
			.domain([1, maxRank])
			.range([m.left, width - m.right])
	);
	const ext = Math.max(...games.map((g) => Math.abs(g.magic)));
	const y = $derived(
		scaleLinear()
			.domain([-ext, ext])
			.range([height - m.bottom, m.top])
			.nice()
	);
	const pts = $derived(games.map((g) => ({ x: x(g.rank), y: y(g.magic), d: g })));
	const find = $derived(nearest(pts, 20));
	const path = $derived(
		line<(typeof binned)[number]>()
			.x((d) => x(d.x))
			.y((d) => y(d.y))
			.curve(curveMonotoneX)(binned) ?? ''
	);
	const ticks = [1, 10, 50, 100, 500, 1000, 2000].filter((t) => t <= maxRank);
</script>

<figure class="wrap" bind:clientWidth={width} use:inview={() => (shown = true)}>
	<ul class="legend">
		<li><span class="swatch dot" style:background="var(--neutral-dot)"></span>One game</li>
		<li>
			<span class="swatch line" style:background="var(--series-1)"></span>Average for that rank band
		</li>
	</ul>
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
	<svg
		{width}
		{height}
		role="img"
		aria-label="Magic sauce by BGG rank"
		onpointermove={(e) => (hover = find(e))}
		onpointerleave={() => (hover = null)}
		onclick={() => hover && openGame(hover.d.id)}
	>
		<g class="grid">
			{#each y.ticks(5) as t (t)}
				<line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} />
			{/each}
		</g>
		<line class="zero" x1={m.left} x2={width - m.right} y1={y(0)} y2={y(0)} />
		{#each pts as p (p.d.id)}
			<circle cx={p.x} cy={p.y} r="2.4" class="dot" class:hl={hover?.d.id === p.d.id} />
		{/each}
		<path d={path} class="curve" class:shown pathLength="1" />
		{#each binned as b (b.lo)}
			<circle cx={x(b.x)} cy={y(b.y)} r="4.5" class="bin" class:shown />
		{/each}
		<g class="axis">
			{#each ticks as t (t)}
				<text x={x(t)} y={height - m.bottom + 18} text-anchor="middle">#{fmt.int(t)}</text>
			{/each}
			{#each y.ticks(5) as t (t)}
				<text x={m.left - 8} y={y(t)} dy="0.35em" text-anchor="end">{fmt.signed(t, 1)}</text>
			{/each}
		</g>
		<text class="axis-title" x={width - m.right} y={height - 4} text-anchor="end"
			>BGG rank (log scale) →</text
		>
	</svg>
	{#if hover}
		<Tooltip x={hover.x} y={hover.y} {width}>
			<span class="t">{hover.d.name}</span>
			<div class="row"><span>Rank</span><span class="v">#{hover.d.rank}</span></div>
			<div class="row">
				<span>Magic sauce</span><span class="v">{fmt.signed(hover.d.magic)}</span>
			</div>
		</Tooltip>
	{/if}
	<details class="table-view">
		<summary>Table view</summary>
		<table>
			<thead><tr><th>Ranks</th><th>Games</th><th>Mean magic sauce</th></tr></thead>
			<tbody>
				{#each binned as b (b.lo)}
					<tr><td>#{b.lo}–{b.hi}</td><td>{b.n}</td><td>{fmt.signed(b.y, 3)}</td></tr>
				{/each}
			</tbody>
		</table>
	</details>
</figure>

<style>
	.wrap {
		position: relative;
		margin: 0;
	}
	svg {
		display: block;
		overflow: visible;
		cursor: crosshair;
	}
	.dot {
		fill: var(--neutral-dot);
		opacity: 0.6;
	}
	.dot.hl {
		fill: var(--text-primary);
		opacity: 1;
	}
	.zero {
		stroke: var(--axis);
	}
	.curve {
		fill: none;
		stroke: var(--series-1);
		stroke-width: 2.5;
		stroke-dasharray: 1;
		stroke-dashoffset: 1;
		transition: stroke-dashoffset 1.6s cubic-bezier(0.65, 0, 0.35, 1);
	}
	.curve.shown {
		stroke-dashoffset: 0;
	}
	.bin {
		fill: var(--series-1);
		stroke: var(--surface-1);
		stroke-width: 2;
		opacity: 0;
		transition: opacity 0.4s 1.4s;
	}
	.bin.shown {
		opacity: 1;
	}
</style>
