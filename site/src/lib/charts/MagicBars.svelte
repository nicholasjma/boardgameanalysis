<script lang="ts">
	import { scaleLinear } from 'd3';
	import { data, fit, fmt, type Game } from '#lib/data.ts';
	import { inview } from '#lib/inview.ts';
	import { openGame } from '#lib/state.svelte.ts';

	const scopes = [
		{ label: 'Top 100', max: 100 },
		{ label: 'Top 500', max: 500 },
		{ label: `All ${fmt.int(data.meta.games)}`, max: Infinity }
	];
	let scope = $state(1);
	let k = $state(10);
	let width = $state(600);
	let shown = $state(false);

	const pool = $derived(data.games.filter((g) => g.rank <= scopes[scope].max));
	const top = $derived([...pool].sort((a, b) => b.magic - a.magic).slice(0, k));
	const bottom = $derived(
		[...pool]
			.sort((a, b) => a.magic - b.magic)
			.slice(0, k)
			.reverse()
	);
	const rows = $derived<(Game | null)[]>([...top, null, ...bottom]);

	const rowH = 26;
	const barH = 14;
	const labelW = $derived(Math.min(260, width * 0.44));
	const ext = $derived(Math.max(...rows.map((g) => (g ? Math.abs(g.magic) : 0))));
	const x = $derived(
		scaleLinear()
			.domain([-ext, ext])
			.range([labelW + 8, width - 48])
	);
	const height = $derived(rows.length * rowH + 30);

	function bar(v: number) {
		const x0 = x(0);
		const x1 = x(shown ? v : 0);
		const w = Math.abs(x1 - x0);
		const r = Math.min(4, w / 2);
		const y0 = (rowH - barH) / 2;
		const y1 = y0 + barH;
		if (v >= 0)
			return `M${x0},${y0} H${x1 - r} Q${x1},${y0} ${x1},${y0 + r} V${y1 - r} Q${x1},${y1} ${x1 - r},${y1} H${x0} Z`;
		return `M${x0},${y0} H${x1 + r} Q${x1},${y0} ${x1},${y0 + r} V${y1 - r} Q${x1},${y1} ${x1 + r},${y1} H${x0} Z`;
	}
</script>

<figure use:inview={() => (shown = true)} bind:clientWidth={width}>
	<div class="controls" role="group" aria-label="Which games to rank">
		{#each scopes as s, i (s.label)}
			<button class="chip" aria-pressed={scope === i} onclick={() => (scope = i)}>{s.label}</button>
		{/each}
		<span class="sep"></span>
		{#each [10, 15] as n (n)}
			<button class="chip" aria-pressed={k === n} onclick={() => (k = n)}>{n} each</button>
		{/each}
	</div>
	<ul class="legend">
		<li><span class="swatch" style:background="var(--div-pos)"></span>Rated above prediction</li>
		<li><span class="swatch" style:background="var(--div-neg)"></span>Rated below prediction</li>
	</ul>
	<svg
		{width}
		{height}
		role="img"
		aria-label="Games rated furthest above and below their predicted rating"
	>
		<line class="zero" x1={x(0)} x2={x(0)} y1="0" y2={height - 26} />
		{#each rows as g, i (g ? g.id : 'gap')}
			<g transform="translate(0,{i * rowH})">
				{#if g}
					<g
						class="row"
						role="button"
						tabindex="0"
						aria-label="{g.name}: {fmt.signed(g.magic)}"
						onclick={() => openGame(g.id)}
						onkeydown={(e) => e.key === 'Enter' && openGame(g.id)}
					>
						<rect class="hit" x="0" y="0" {width} height={rowH} />
						<text class="name" x={labelW - 4} y={rowH / 2} dy="0.35em" text-anchor="end">
							<tspan class="rank">#{g.rank}</tspan>
							<title>{g.name}</title>{fit(g.name, labelW - 48)}
						</text>
						<path
							d={bar(g.magic)}
							fill={g.magic >= 0 ? 'var(--div-pos)' : 'var(--div-neg)'}
							class="bar"
							style:transition-delay="{i * 25}ms"
						/>
						<text
							class="val"
							x={x(g.magic) + (g.magic >= 0 ? 6 : -6)}
							y={rowH / 2}
							dy="0.35em"
							text-anchor={g.magic >= 0 ? 'start' : 'end'}
							class:shown
						>
							{fmt.signed(g.magic)}
						</text>
					</g>
				{:else}
					<line class="gap" x1={labelW / 2} x2={width - 48} y1={rowH / 2} y2={rowH / 2} />
				{/if}
			</g>
		{/each}
		<g class="axis" transform="translate(0,{height - 10})">
			{#each x.ticks(5) as t (t)}
				<text x={x(t)} text-anchor="middle">{fmt.signed(t, 1)}</text>
			{/each}
		</g>
	</svg>
</figure>

<style>
	figure {
		margin: 0;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 0.75rem;
		align-items: center;
	}
	.sep {
		width: 1px;
		height: 18px;
		background: var(--grid);
		margin: 0 0.3rem;
	}
	.row {
		cursor: pointer;
		outline: none;
	}
	.row:hover .name,
	.row:focus-visible .name {
		fill: var(--text-primary);
	}
	.row:focus-visible .hit {
		fill: var(--surface-2);
	}
	.hit {
		fill: transparent;
	}
	.name {
		fill: var(--text-secondary);
		font-size: 12.5px;
	}
	.rank {
		fill: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.val {
		fill: var(--text-muted);
		font-size: 11.5px;
		font-variant-numeric: tabular-nums;
		opacity: 0;
		transition: opacity 0.3s 0.6s;
	}
	.val.shown {
		opacity: 1;
	}
	.bar {
		transition: d 0.8s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.zero {
		stroke: var(--axis);
	}
	.gap {
		stroke: var(--grid);
	}
</style>
