<script lang="ts">
	import { scaleLinear } from 'd3';
	import { data, fit, kindLabel, type Kind } from '#lib/data.ts';
	import { inview } from '#lib/inview.ts';

	let { n = 14 }: { n?: number } = $props();

	const kindColor: Record<Kind, string> = {
		numeric: 'var(--series-1)',
		mechanic: 'var(--series-2)',
		category: 'var(--series-3)'
	};

	const rows = $derived(data.importance.slice(0, n));
	let width = $state(600);
	let shown = $state(false);
	let hover = $state<number | null>(null);

	const rowH = 30;
	const barH = 16;
	const labelW = $derived(Math.min(240, width * 0.42));
	const x = $derived(
		scaleLinear()
			.domain([0, Math.max(...rows.map((r) => r.meanAbs))])
			.range([0, width - labelW - 56])
	);
	const height = $derived(rows.length * rowH + 8);

	// Rounded data-end, square at the baseline.
	function bar(w: number) {
		const r = Math.min(4, w / 2);
		const y0 = (rowH - barH) / 2;
		return `M0,${y0} H${w - r} Q${w},${y0} ${w},${y0 + r} V${y0 + barH - r} Q${w},${y0 + barH} ${w - r},${y0 + barH} H0 Z`;
	}
</script>

<figure use:inview={() => (shown = true)} bind:clientWidth={width}>
	<ul class="legend">
		{#each ['numeric', 'mechanic', 'category'] as const as k (k)}
			<li><span class="swatch" style:background={kindColor[k]}></span>{kindLabel[k]}</li>
		{/each}
	</ul>
	<svg {width} {height} role="img" aria-label="Bar chart of the {n} most influential features">
		{#each rows as r, i (r.feature)}
			{@const w = shown ? Math.max(2, x(r.meanAbs)) : 0}
			<g
				transform="translate(0,{i * rowH})"
				class="row"
				class:dim={hover !== null && hover !== i}
				role="listitem"
				onpointerenter={() => (hover = i)}
				onpointerleave={() => (hover = null)}
			>
				<rect class="hit" x="0" y="0" {width} height={rowH} />
				<text class="name" x={labelW - 10} y={rowH / 2} dy="0.35em" text-anchor="end">
					<title>{r.feature}</title>{fit(r.feature, labelW - 14)}
				</text>
				<g transform="translate({labelW},0)">
					<path
						d={bar(w)}
						fill={kindColor[r.kind]}
						style:transition-delay="{i * 45}ms"
						class="bar"
					/>
					<text class="val" x={w + 6} y={rowH / 2} dy="0.35em" class:shown>
						±{r.meanAbs.toFixed(3)}
					</text>
				</g>
			</g>
		{/each}
	</svg>
	<details class="table-view">
		<summary>Table view</summary>
		<div class="scroll">
			<table>
				<thead><tr><th>Feature</th><th>Kind</th><th>Mean |SHAP|</th></tr></thead>
				<tbody>
					{#each data.importance as r (r.feature)}
						<tr><td>{r.feature}</td><td>{kindLabel[r.kind]}</td><td>{r.meanAbs.toFixed(4)}</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
</figure>

<style>
	figure {
		margin: 0;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.hit {
		fill: transparent;
	}
	.row {
		transition: opacity 0.2s;
	}
	.row.dim {
		opacity: 0.35;
	}
	.name {
		fill: var(--text-secondary);
		font-size: 13px;
	}
	.val {
		fill: var(--text-muted);
		font-size: 11.5px;
		font-variant-numeric: tabular-nums;
		opacity: 0;
		transition: opacity 0.4s 0.6s;
	}
	.val.shown {
		opacity: 1;
	}
	.bar {
		transition: d 0.9s cubic-bezier(0.22, 1, 0.36, 1);
	}
</style>
