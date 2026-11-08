<script lang="ts">
	import { Delaunay, scaleLinear } from 'd3';
	import { data, fmt, type Game } from '#lib/data.ts';
	import { eraColor } from '#lib/era.ts';
	import { inview } from '#lib/inview.ts';
	import { openGame } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';
	import EraLegend from '#lib/components/EraLegend.svelte';

	const STEP = 0.1;
	const lo = Math.floor(Math.min(...data.games.map((g) => g.rating)) * 10) / 10;
	const hi = Math.ceil(Math.max(...data.games.map((g) => g.rating)) * 10) / 10 + STEP;
	const nBins = Math.round((hi - lo) / STEP);

	// Each bin stacks its games oldest-at-the-bottom so the era gradient reads upward.
	const bins: Game[][] = Array.from({ length: nBins }, () => []);
	for (const g of data.games) bins[Math.min(nBins - 1, Math.floor((g.rating - lo) / STEP))].push(g);
	for (const b of bins) b.sort((a, c) => a.year - c.year);
	const maxBin = Math.max(...bins.map((b) => b.length));

	let width = $state(900);
	let shown = $state(false);
	let hover = $state<{ g: Game; x: number; y: number } | null>(null);

	const m = { top: 28, right: 8, bottom: 34, left: 8 };
	const layout = $derived.by(() => {
		const inner = width - m.left - m.right;
		const colW = inner / nBins;
		const perRow = Math.max(2, Math.floor(colW / 6.5));
		const pitch = colW / perRow;
		const rows = Math.ceil(maxBin / perRow);
		const height = rows * pitch + m.top + m.bottom;
		const x = scaleLinear()
			.domain([lo, hi])
			.range([m.left, width - m.right]);
		const dots = bins.flatMap((b, bi) =>
			b.map((g, i) => ({
				g,
				cx: m.left + bi * colW + (i % perRow) * pitch + pitch / 2,
				cy: height - m.bottom - Math.floor(i / perRow) * pitch - pitch / 2,
				delay: bi * 18 + Math.floor(i / perRow) * 6
			}))
		);
		return { height, r: Math.max(1.2, pitch * 0.4), x, dots };
	});

	const delaunay = $derived(
		Delaunay.from(
			layout.dots,
			(d) => d.cx,
			(d) => d.cy
		)
	);

	function onMove(e: PointerEvent) {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		const px = e.clientX - rect.left;
		const py = e.clientY - rect.top;
		const i = delaunay.find(px, py);
		const d = layout.dots[i];
		hover = d && Math.hypot(d.cx - px, d.cy - py) < 24 ? { g: d.g, x: d.cx, y: d.cy } : null;
	}

	const mean = data.meta.meanRating;
	const ticks = $derived(layout.x.ticks(width < 520 ? 4 : 8));
</script>

<figure class="wrap" bind:clientWidth={width} use:inview={() => (shown = true)}>
	<EraLegend />
	<!-- Pointer hover is an enhancement; keyboard users reach every game via search and the table. -->
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
	<svg
		{width}
		height={layout.height}
		role="img"
		aria-label="Dot chart: each of {data.meta
			.games} games placed by its average rating, colored by year published"
		onpointermove={onMove}
		onpointerleave={() => (hover = null)}
		onclick={() => hover && openGame(hover.g.id)}
	>
		<line
			class="mean"
			x1={layout.x(mean)}
			x2={layout.x(mean)}
			y1={m.top - 10}
			y2={layout.height - m.bottom}
		/>
		<text class="mean-label" x={layout.x(mean) + 6} y={m.top - 2}>
			Average {fmt.r2(mean)}
		</text>
		<g class:shown>
			{#each layout.dots as d (d.g.id)}
				<circle
					cx={d.cx}
					cy={d.cy}
					r={layout.r}
					fill={eraColor(d.g.year)}
					style:transition-delay="{d.delay}ms"
					class:hl={hover?.g.id === d.g.id}
				/>
			{/each}
		</g>
		<g class="axis">
			<line
				x1={m.left}
				x2={width - m.right}
				y1={layout.height - m.bottom + 4}
				y2={layout.height - m.bottom + 4}
			/>
			{#each ticks as t (t)}
				<text x={layout.x(t)} y={layout.height - m.bottom + 20} text-anchor="middle"
					>{t.toFixed(1)}</text
				>
			{/each}
		</g>
		<text class="axis-title" x={width - m.right} y={layout.height - 2} text-anchor="end">
			Average rating →
		</text>
	</svg>
	{#if hover}
		<Tooltip x={hover.x} y={hover.y + 40} {width}>
			<span class="t">{hover.g.name}</span>
			<div class="row"><span>Rating</span><span class="v">{fmt.r2(hover.g.rating)}</span></div>
			<div class="row"><span>Rank</span><span class="v">#{hover.g.rank}</span></div>
			<div class="row"><span>Year</span><span class="v">{hover.g.year}</span></div>
		</Tooltip>
	{/if}
</figure>

<style>
	.wrap {
		position: relative;
		margin: 0;
	}
	svg {
		display: block;
		cursor: crosshair;
		overflow: visible;
	}
	circle {
		opacity: 0;
		transform: translateY(-40px);
		transform-box: fill-box;
		transition:
			opacity 0.5s ease,
			transform 0.7s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.shown circle {
		opacity: 1;
		transform: none;
	}
	circle.hl {
		stroke: var(--text-primary);
		stroke-width: 2;
	}
	.mean {
		stroke: var(--text-muted);
		stroke-width: 1;
	}
	.mean-label {
		fill: var(--text-secondary);
		font-size: 12px;
	}
</style>
