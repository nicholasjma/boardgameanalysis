<script lang="ts">
	import { scaleLinear } from 'd3';
	import { fmt, type Game } from '#lib/data.ts';

	let { game }: { game: Game } = $props();

	interface Step {
		label: string;
		from: number;
		to: number;
		total?: boolean;
	}

	const steps = $derived.by(() => {
		const why = game.why;
		if (!why) return [] as Step[];
		const out: Step[] = [{ label: 'Typical game', from: 0, to: why.base, total: true }];
		let acc = why.base;
		for (const [label, v] of why.parts) {
			out.push({ label, from: acc, to: acc + v });
			acc += v;
		}
		out.push({ label: 'All other traits', from: acc, to: acc + why.other });
		out.push({ label: 'Predicted', from: 0, to: game.pred, total: true });
		out.push({ label: 'Magic sauce', from: game.pred, to: game.rating });
		out.push({ label: 'Actual rating', from: 0, to: game.rating, total: true });
		return out;
	});

	let width = $state(420);
	const rowH = 24;
	const labelW = 150;
	const lo = $derived(
		Math.min(
			...steps.filter((s) => !s.total).flatMap((s) => [s.from, s.to]),
			game.pred,
			game.rating
		) - 0.15
	);
	const hi = $derived(Math.max(...steps.flatMap((s) => [s.to]), game.pred, game.rating) + 0.15);
	const x = $derived(
		scaleLinear()
			.domain([lo, hi])
			.range([labelW + 6, width - 44])
	);
	const height = $derived(steps.length * rowH + 24);
</script>

<div bind:clientWidth={width}>
	<svg
		{width}
		{height}
		role="img"
		aria-label="How {game.name}'s predicted rating is built up, step by step"
	>
		<g class="grid">
			{#each x.ticks(4) as t (t)}
				<line x1={x(t)} x2={x(t)} y1="0" y2={height - 20} />
			{/each}
		</g>
		{#each steps as s, i (s.label + i)}
			{@const a = s.total ? x(lo) : x(Math.min(s.from, s.to))}
			{@const b = x(s.total ? s.to : Math.max(s.from, s.to))}
			{@const up = s.to >= s.from}
			<g transform="translate(0,{i * rowH})">
				<text class="lbl" class:tot={s.total} x={labelW} y={rowH / 2} dy="0.35em" text-anchor="end">
					{s.label}
				</text>
				<rect
					x={a}
					y={(rowH - 14) / 2}
					width={Math.max(2, b - a)}
					height="14"
					rx="3"
					fill={s.total ? 'var(--neutral-dot)' : up ? 'var(--div-pos)' : 'var(--div-neg)'}
					class="bar"
					style:transition-delay="{i * 50}ms"
				/>
				{#if i < steps.length - 1 && !steps[i + 1].total && !s.total}
					<line
						class="link"
						x1={x(s.to)}
						x2={x(s.to)}
						y1={(rowH + 14) / 2}
						y2={rowH + (rowH - 14) / 2}
					/>
				{/if}
				<text class="v" x={b + 6} y={rowH / 2} dy="0.35em">
					{s.total ? fmt.r2(s.to) : fmt.signed(s.to - s.from, 2)}
				</text>
			</g>
		{/each}
		<g class="axis">
			{#each x.ticks(4) as t (t)}
				<text x={x(t)} y={height - 4} text-anchor="middle">{t.toFixed(1)}</text>
			{/each}
		</g>
	</svg>
</div>

<style>
	svg {
		display: block;
		overflow: visible;
	}
	.lbl {
		font-size: 12px;
		fill: var(--text-secondary);
	}
	.lbl.tot {
		fill: var(--text-primary);
		font-weight: 600;
	}
	.v {
		font-size: 11px;
		fill: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.link {
		stroke: var(--text-muted);
		stroke-width: 1;
	}
	.bar {
		animation: grow 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
		transform-box: fill-box;
		transform-origin: left;
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
			opacity: 0;
		}
	}
</style>
