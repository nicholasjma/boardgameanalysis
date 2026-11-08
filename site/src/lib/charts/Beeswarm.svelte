<script lang="ts">
	import { scaleLinear } from 'd3';
	import { data, fit, fmt } from '#lib/data.ts';
	import { inview } from '#lib/inview.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	let { n = 12 }: { n?: number } = $props();

	const rows = $derived(data.beeswarm.slice(0, n));
	const ext = $derived(Math.max(...rows.flatMap((r) => r.points.map((p) => Math.abs(p[0])))));

	let width = $state(700);
	let shown = $state(false);
	let hover = $state<{ i: number; y: number } | null>(null);

	const rowH = 34;
	const m = { top: 8, bottom: 40 };
	const labelW = $derived(Math.min(220, width * 0.36));
	const x = $derived(
		scaleLinear()
			.domain([-ext, ext])
			.range([labelW, width - 12])
			.nice()
	);
	const height = $derived(rows.length * rowH + m.top + m.bottom);

	// Feature value (0..1) → five-step ordinal ramp: low values light, high values dark.
	const step = (v: number) => `var(--ord-${Math.min(5, 1 + Math.floor(v * 5))})`;

	// Deterministic dodge: stack points that share an x-bin, alternating above/below the row.
	const laid = $derived(
		rows.map((r) => {
			const binW = 3;
			const counts: Record<number, number> = {};
			return r.points.map(([s, v]) => {
				const px = x(s);
				const bin = Math.round(px / binW);
				const k = counts[bin] ?? 0;
				counts[bin] = k + 1;
				const off = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 2.6;
				return { px, dy: Math.max(-rowH / 2 + 3, Math.min(rowH / 2 - 3, off)), fill: step(v) };
			});
		})
	);
</script>

<figure class="wrap" use:inview={() => (shown = true)} bind:clientWidth={width}>
	<ul class="legend">
		<li class="ttl">Feature value</li>
		<li><span class="swatch dot" style:background="var(--ord-1)"></span>Low / absent</li>
		<li><span class="swatch dot" style:background="var(--ord-3)"></span>Mid</li>
		<li><span class="swatch dot" style:background="var(--ord-5)"></span>High / present</li>
	</ul>
	<svg
		{width}
		{height}
		role="img"
		aria-label="Beeswarm of SHAP values for the {n} most important features"
	>
		<g class="grid">
			{#each x.ticks(6) as t (t)}
				<line x1={x(t)} x2={x(t)} y1={m.top} y2={height - m.bottom} />
			{/each}
		</g>
		<line class="zero" x1={x(0)} x2={x(0)} y1={m.top - 4} y2={height - m.bottom} />
		{#each rows as r, i (r.feature)}
			{@const cy = m.top + i * rowH + rowH / 2}
			<g
				class="row"
				class:dim={hover !== null && hover.i !== i}
				role="listitem"
				onpointerenter={() => (hover = { i, y: cy })}
				onpointerleave={() => (hover = null)}
			>
				<rect class="hit" x="0" y={cy - rowH / 2} {width} height={rowH} />
				<text class="name" x={labelW - 12} y={cy} dy="0.35em" text-anchor="end"
					><title>{r.feature}</title>{fit(r.feature, labelW - 16)}</text
				>
				{#each laid[i] as p, j (j)}
					<circle
						cx={shown ? p.px : x(0)}
						cy={cy + (shown ? p.dy : 0)}
						r="2.1"
						fill={p.fill}
						style:transition-delay="{i * 40 + (j % 40) * 4}ms"
					/>
				{/each}
			</g>
		{/each}
		<g class="axis" transform="translate(0,{height - m.bottom + 6})">
			{#each x.ticks(6) as t (t)}
				<text x={x(t)} y="12" text-anchor="middle">{fmt.signed(t, 2)}</text>
			{/each}
		</g>
		<text class="axis-title" x={x(0) - 8} y={height - 6} text-anchor="end"
			>← lowers predicted rating</text
		>
		<text class="axis-title" x={x(0) + 8} y={height - 6}>raises predicted rating →</text>
	</svg>
	{#if hover}
		{@const r = rows[hover.i]}
		{@const pos = r.points.filter((p) => p[1] > 0.5)}
		{@const neg = r.points.filter((p) => p[1] <= 0.5)}
		<Tooltip x={labelW + 40} y={hover.y} {width}>
			<span class="t">{r.feature}</span>
			<div class="row">
				<span>Mean |impact|</span><span class="v">±{r.meanAbs.toFixed(3)}</span>
			</div>
			{#if r.kind !== 'numeric' && pos.length}
				<div class="row">
					<span>When present</span>
					<span class="v">{fmt.signed(pos.reduce((a, p) => a + p[0], 0) / pos.length, 3)}</span>
				</div>
				<div class="row">
					<span>When absent</span>
					<span class="v"
						>{fmt.signed(neg.reduce((a, p) => a + p[0], 0) / Math.max(1, neg.length), 3)}</span
					>
				</div>
			{/if}
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
	}
	.ttl {
		color: var(--text-muted);
	}
	.hit {
		fill: transparent;
	}
	.row {
		transition: opacity 0.2s;
	}
	.row.dim {
		opacity: 0.3;
	}
	.name {
		fill: var(--text-secondary);
		font-size: 13px;
	}
	.zero {
		stroke: var(--axis);
		stroke-width: 1;
	}
	circle {
		transition:
			cx 1s cubic-bezier(0.22, 1, 0.36, 1),
			cy 1s cubic-bezier(0.22, 1, 0.36, 1);
	}
</style>
