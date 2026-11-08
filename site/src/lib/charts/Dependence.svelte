<script lang="ts">
	import { bisector, line, curveMonotoneX, scaleLinear, mean, groups } from 'd3';
	import { data, fmt } from '#lib/data.ts';
	import { inview } from '#lib/inview.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	let {
		feature,
		title,
		unit = '',
		binSize,
		clampMax = Infinity
	}: {
		feature: 'years_since_base' | 'avg_time';
		title: string;
		unit?: string;
		binSize: number;
		clampMax?: number;
	} = $props();

	const pts = $derived(data.dependence[feature].filter(([v]) => v <= clampMax));
	const curve = $derived(
		groups(pts, ([v]) => Math.floor(v / binSize) * binSize)
			.map(([b, ps]) => ({ x: b + binSize / 2, y: mean(ps, (p) => p[1]) ?? 0, n: ps.length }))
			.filter((d) => d.n >= 4)
			.sort((a, b) => a.x - b.x)
	);

	let width = $state(400);
	let shown = $state(false);
	let hover = $state<{ x: number; y: number; d: { x: number; y: number; n: number } } | null>(null);
	const height = 240;
	const m = { top: 12, right: 12, bottom: 36, left: 44 };

	const x = $derived(
		scaleLinear()
			.domain([Math.min(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[0]))])
			.range([m.left, width - m.right])
	);
	const yExt = $derived(Math.max(0.05, ...pts.map((p) => Math.abs(p[1]))));
	const y = $derived(
		scaleLinear()
			.domain([-yExt, yExt])
			.range([height - m.bottom, m.top])
			.nice()
	);
	const path = $derived(
		line<{ x: number; y: number }>()
			.x((d) => x(d.x))
			.y((d) => y(d.y))
			.curve(curveMonotoneX)(curve) ?? ''
	);
	const bis = bisector<{ x: number }, number>((d) => d.x).center;

	function onMove(e: PointerEvent) {
		const rect = (e.currentTarget as Element).getBoundingClientRect();
		const v = x.invert(e.clientX - rect.left);
		const d = curve[bis(curve, v)];
		hover = d ? { x: x(d.x), y: y(d.y), d } : null;
	}
	const label = (v: number) =>
		feature === 'years_since_base' ? `${Math.round(v)}` : `${Math.round(v)}${unit}`;
</script>

<figure class="wrap" bind:clientWidth={width} use:inview={() => (shown = true)}>
	<p class="chart-title">{title}</p>
	<svg
		{width}
		{height}
		role="img"
		aria-label="{title}: effect on predicted rating"
		onpointermove={onMove}
		onpointerleave={() => (hover = null)}
	>
		<g class="grid">
			{#each y.ticks(4) as t (t)}
				<line x1={m.left} x2={width - m.right} y1={y(t)} y2={y(t)} />
			{/each}
		</g>
		<line class="zero" x1={m.left} x2={width - m.right} y1={y(0)} y2={y(0)} />
		{#each pts as p, i (i)}
			<circle cx={x(p[0])} cy={y(p[1])} r="2.2" class="dot" />
		{/each}
		<path d={path} class="curve" class:shown pathLength="1" />
		<g class="axis">
			{#each y.ticks(4) as t (t)}
				<text x={m.left - 8} y={y(t)} dy="0.35em" text-anchor="end">{fmt.signed(t, 2)}</text>
			{/each}
			{#each x.ticks(width < 360 ? 3 : 5) as t (t)}
				<text x={x(t)} y={height - m.bottom + 18} text-anchor="middle">{label(t)}</text>
			{/each}
		</g>
		{#if hover}
			<line class="cross" x1={hover.x} x2={hover.x} y1={m.top} y2={height - m.bottom} />
			<circle cx={hover.x} cy={hover.y} r="5" class="end" />
		{/if}
	</svg>
	{#if hover}
		<Tooltip x={hover.x} y={hover.y} {width}>
			<div class="row">
				<span class="v">{fmt.signed(hover.d.y, 3)}</span><span>avg effect</span>
			</div>
			<div class="row">
				<span>{feature === 'years_since_base' ? 'Around' : 'Around'}</span><span class="v"
					>{label(hover.d.x)}</span
				>
			</div>
			<div class="row"><span>Games</span><span class="v">{hover.d.n}</span></div>
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
		overflow: visible;
		cursor: crosshair;
	}
	.dot {
		fill: var(--neutral-dot);
		opacity: 0.55;
	}
	.zero {
		stroke: var(--axis);
	}
	.curve {
		fill: none;
		stroke: var(--series-1);
		stroke-width: 2.5;
		stroke-linecap: round;
		stroke-linejoin: round;
		stroke-dasharray: 1;
		stroke-dashoffset: 1;
		transition: stroke-dashoffset 1.6s cubic-bezier(0.65, 0, 0.35, 1);
	}
	.curve.shown {
		stroke-dashoffset: 0;
	}
	.cross {
		stroke: var(--text-muted);
		stroke-width: 1;
	}
	.end {
		fill: var(--series-1);
		stroke: var(--surface-1);
		stroke-width: 2;
	}
</style>
