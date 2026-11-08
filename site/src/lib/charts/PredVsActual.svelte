<script lang="ts">
	import { scaleLinear, scaleSqrt } from 'd3';
	import { data, fmt, type Game } from '#lib/data.ts';
	import { eraColor } from '#lib/era.ts';
	import { inview } from '#lib/inview.ts';
	import { nearest, type Pt } from '#lib/nearest.ts';
	import { openGame, ui } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';
	import EraLegend from '#lib/components/EraLegend.svelte';

	const games = data.games;
	let width = $state(700);
	let shown = $state(false);
	let hover = $state<Pt<Game> | null>(null);

	const height = $derived(Math.min(560, Math.max(360, width * 0.7)));
	const m = { top: 16, right: 16, bottom: 44, left: 48 };
	const lo = Math.floor(Math.min(...games.map((g) => Math.min(g.pred, g.rating))) * 4) / 4;
	const hi = Math.ceil(Math.max(...games.map((g) => Math.max(g.pred, g.rating))) * 4) / 4;

	const x = $derived(
		scaleLinear()
			.domain([lo, hi])
			.range([m.left, width - m.right])
	);
	const y = $derived(
		scaleLinear()
			.domain([lo, hi])
			.range([height - m.bottom, m.top])
	);
	const r = scaleSqrt()
		.domain([0, Math.max(...games.map((g) => g.votes))])
		.range([1.5, 9]);

	const pts = $derived(games.map((g) => ({ x: x(g.pred), y: y(g.rating), d: g })));
	const find = $derived(nearest(pts, 24));

	// Annotate the biggest over- and under-performers among well-known games.
	const callouts = $derived.by(() => {
		const popular = games.filter((g) => g.votes > 8000);
		const over = [...popular].sort((a, b) => b.magic - a.magic).slice(0, 6);
		const under = [...popular].sort((a, b) => a.magic - b.magic).slice(0, 4);
		// Greedy placement: keep a label only if its box clears every label already placed.
		const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
		const keep = [];
		for (const g of [...over, ...under]) {
			const w = g.name.length * 6.8;
			const ax = x(g.pred) + (g.magic > 0 ? -12 : 12);
			const box = {
				x0: g.magic > 0 ? ax - w : ax,
				x1: g.magic > 0 ? ax : ax + w,
				y0: y(g.rating) - 9,
				y1: y(g.rating) + 9
			};
			const hit = placed.some(
				(b) => box.x0 < b.x1 && box.x1 > b.x0 && box.y0 < b.y1 && box.y1 > b.y0
			);
			if (!hit && box.x0 > m.left && box.x1 < width - m.right) {
				placed.push(box);
				keep.push(g);
			}
			if (keep.length >= 5) break;
		}
		return keep;
	});
	const focus = $derived(ui.hoverGame ?? hover?.d.id ?? null);
</script>

<figure class="wrap" bind:clientWidth={width} use:inview={() => (shown = true)}>
	<EraLegend />
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
	<svg
		{width}
		{height}
		role="img"
		aria-label="Scatter plot of predicted versus actual rating for every game"
		onpointermove={(e) => (hover = find(e))}
		onpointerleave={() => (hover = null)}
		onclick={() => hover && openGame(hover.d.id)}
	>
		<g class="grid">
			{#each x.ticks(6) as t (t)}
				<line x1={x(t)} x2={x(t)} y1={m.top} y2={height - m.bottom} />
				<line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} />
			{/each}
		</g>
		<line class="diag" x1={x(lo)} y1={y(lo)} x2={x(hi)} y2={y(hi)} />
		<text class="diag-label" x={x(hi) - 6} y={y(hi) + 16} text-anchor="end">
			predicted = actual
		</text>
		<text class="zone" x={m.left + 10} y={m.top + 16}>Better than its traits suggest ↑</text>
		<text class="zone" x={width - m.right - 10} y={height - m.bottom - 10} text-anchor="end">
			↓ Worse than its traits suggest
		</text>
		<g class="dots" class:shown>
			{#each pts as p, i (p.d.id)}
				<circle
					cx={p.x}
					cy={p.y}
					r={r(p.d.votes)}
					fill={eraColor(p.d.year)}
					style:transition-delay="{(i % 200) * 3}ms"
				/>
			{/each}
		</g>
		{#each callouts as g (g.id)}
			<g class="callout" class:shown>
				<circle cx={x(g.pred)} cy={y(g.rating)} r={r(g.votes) + 3} class="ring" />
				<text
					x={x(g.pred) + (g.magic > 0 ? -12 : 12)}
					y={y(g.rating)}
					dy="0.35em"
					text-anchor={g.magic > 0 ? 'end' : 'start'}
				>
					{g.name}
				</text>
			</g>
		{/each}
		{#if focus !== null}
			{@const g = games.find((d) => d.id === focus)}
			{#if g}
				<circle cx={x(g.pred)} cy={y(g.rating)} r={r(g.votes) + 4} class="focus" />
			{/if}
		{/if}
		<g class="axis">
			{#each x.ticks(6) as t (t)}
				<text x={x(t)} y={height - m.bottom + 18} text-anchor="middle">{t.toFixed(1)}</text>
				<text x={m.left - 8} y={y(t)} dy="0.35em" text-anchor="end">{t.toFixed(1)}</text>
			{/each}
		</g>
		<text class="axis-title" x={width - m.right} y={height - 6} text-anchor="end">
			Predicted rating (from year, play time, categories & mechanics) →
		</text>
		<text class="axis-title" transform="translate(12,{m.top}) rotate(90)"
			>Actual average rating →</text
		>
	</svg>
	{#if hover}
		<Tooltip x={hover.x} y={hover.y} {width}>
			<span class="t">{hover.d.name} <span class="muted">({hover.d.year})</span></span>
			<div class="row"><span>Actual</span><span class="v">{fmt.r2(hover.d.rating)}</span></div>
			<div class="row"><span>Predicted</span><span class="v">{fmt.r2(hover.d.pred)}</span></div>
			<div class="row">
				<span>Magic sauce</span><span class="v">{fmt.signed(hover.d.magic)}</span>
			</div>
			<div class="row"><span>Votes</span><span class="v">{fmt.int(hover.d.votes)}</span></div>
		</Tooltip>
	{/if}
	<p class="foot">Dot size = number of ratings. Click any game for its breakdown.</p>
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
	.diag {
		stroke: var(--text-muted);
		stroke-width: 1;
	}
	.diag-label,
	.zone {
		fill: var(--text-muted);
		font-size: 11.5px;
	}
	.dots circle {
		opacity: 0;
		transition: opacity 0.6s;
		stroke: var(--surface-1);
		stroke-width: 0.6;
	}
	.dots.shown circle {
		opacity: 0.75;
	}
	.callout {
		opacity: 0;
		transition: opacity 0.6s 1.2s;
	}
	.callout.shown {
		opacity: 1;
	}
	.callout text {
		fill: var(--text-primary);
		font-size: 12px;
		font-weight: 600;
		paint-order: stroke;
		stroke: var(--surface-1);
		stroke-width: 4px;
		stroke-linejoin: round;
	}
	.ring {
		fill: none;
		stroke: var(--text-secondary);
		stroke-width: 1;
	}
	.focus {
		fill: none;
		stroke: var(--text-primary);
		stroke-width: 2;
	}
	.foot {
		font-size: 0.8rem;
		color: var(--text-muted);
		margin: 0.4rem 0 0;
	}
	:global(.muted) {
		color: var(--text-muted);
		font-weight: 400;
	}
</style>
