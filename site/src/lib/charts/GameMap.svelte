<script lang="ts">
	import { hierarchy, pack, type HierarchyCircularNode } from 'd3';
	import { data, fit, fmt, gamesById, type Game } from '#lib/data.ts';
	import { ratingBand, ratingBands } from '#lib/era.ts';
	import { inview } from '#lib/inview.ts';
	import { openGame } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	type Node = { name: string; cluster?: number; game?: Game; children?: Node[]; value?: number };

	const mapped = data.games.filter((g) => g.cluster !== undefined);
	const bands = ratingBands;
	const band = ratingBand;

	const tree: Node = {
		name: 'root',
		children: data.clusters.map((c) => ({
			name: c.name,
			cluster: c.id,
			children: mapped
				.filter((g) => g.cluster === c.id)
				.map((g) => ({ name: g.name, game: g, value: Math.sqrt(g.votes) }))
		}))
	};

	let width = $state(800);
	let shown = $state(false);
	let active = $state<number | null>(null);
	let pinned = $state<number | null>(null);
	let hover = $state<{ g: Game; x: number; y: number } | null>(null);
	const focus = $derived(pinned ?? active);
	const height = $derived(Math.min(720, Math.max(420, width * 0.78)));

	const root = $derived(
		pack<Node>()
			.size([width, height])
			.padding((d) => (d.depth === 0 ? 16 : 1.2))(
			hierarchy(tree)
				.sum((d) => d.value ?? 0)
				.sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
		)
	);
	const groups = $derived((root.children ?? []) as HierarchyCircularNode<Node>[]);

	const shortName = (s: string) => s.replace(/\s*\/\s*/g, ' · ');
</script>

<div class="map">
	<div class="list" role="listbox" aria-label="Game families">
		{#each data.clusters as c (c.id)}
			<button
				class="cl"
				role="option"
				aria-selected={pinned === c.id}
				class:on={focus === c.id}
				onpointerenter={() => (active = c.id)}
				onpointerleave={() => (active = null)}
				onfocus={() => (active = c.id)}
				onblur={() => (active = null)}
				onclick={() => (pinned = pinned === c.id ? null : c.id)}
			>
				<span class="nm">{shortName(c.name)}</span>
				<span class="meta">{c.size} games · avg {fmt.r2(c.meanRating)}</span>
			</button>
		{/each}
	</div>

	<div>
		<ul class="legend">
			<li class="ttl">Average rating</li>
			{#each bands as b, i (b.label)}
				<li><span class="swatch dot" style:background="var(--ord-{i + 1})"></span>{b.label}</li>
			{/each}
			<li class="ttl">· bubble size = number of ratings</li>
		</ul>
		<figure class="wrap" bind:clientWidth={width} use:inview={() => (shown = true)}>
			<svg
				{width}
				{height}
				role="img"
				aria-label="The top {mapped.length} games packed into {groups.length} families by shared categories and mechanics"
			>
				{#each groups as gnode, gi (gnode.data.cluster)}
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<g
						class="family"
						class:on={focus === gnode.data.cluster}
						class:off={focus !== null && focus !== gnode.data.cluster}
						onpointerenter={() => (active = gnode.data.cluster ?? null)}
						onpointerleave={() => (active = null)}
					>
						<circle class="hull" cx={gnode.x} cy={gnode.y} r={gnode.r} />
						{#each gnode.children ?? [] as leaf, li (leaf.data.game?.id)}
							{@const g = leaf.data.game!}
							<!-- svelte-ignore a11y_click_events_have_key_events -->
							<circle
								class="game"
								class:shown
								cx={leaf.x}
								cy={leaf.y}
								r={leaf.r}
								fill="var(--ord-{band(g.rating)})"
								style:transition-delay="{gi * 70 + li * 4}ms"
								role="button"
								tabindex="-1"
								aria-label={g.name}
								onpointerenter={() => (hover = { g, x: leaf.x, y: leaf.y })}
								onpointerleave={() => (hover = null)}
								onclick={() => openGame(g.id)}
							/>
						{/each}
					</g>
				{/each}
				{#each groups as gnode (gnode.data.cluster)}
					{@const label = shortName(gnode.data.name)}
					<text
						class="label"
						class:shown
						class:off={focus !== null && focus !== gnode.data.cluster}
						x={gnode.x}
						y={gnode.y - gnode.r - 6}
						text-anchor="middle"
					>
						<title>{label}</title>{fit(label, Math.max(120, gnode.r * 2.6), 6.4)}
					</text>
				{/each}
			</svg>
			{#if hover}
				<Tooltip x={hover.x} y={hover.y} {width}>
					<span class="t">{hover.g.name}</span>
					<div class="row"><span>Rank</span><span class="v">#{hover.g.rank}</span></div>
					<div class="row"><span>Rating</span><span class="v">{fmt.r2(hover.g.rating)}</span></div>
					<div class="row"><span>Ratings</span><span class="v">{fmt.int(hover.g.votes)}</span></div>
				</Tooltip>
			{/if}
		</figure>
	</div>
</div>

{#if focus !== null}
	{@const c = data.clusters[focus]}
	<div class="detail">
		<div>
			<p class="chart-title">What defines “{shortName(c.name)}”</p>
			{#each c.traits as t (t.name)}
				<div class="trait">
					<span class="tn">{t.name}</span>
					<span class="track"><span class="fill" style:width="{t.share * 100}%"></span></span>
					<span class="tv">{fmt.pct(t.share)}</span>
				</div>
			{/each}
		</div>
		<div>
			<p class="chart-title">Top games</p>
			<ol class="tops">
				{#each c.topGames.slice(0, 6) as id (id)}
					{@const g = gamesById.get(id)}
					{#if g}
						<li><button onclick={() => openGame(id)}>#{g.rank} {g.name}</button></li>
					{/if}
				{/each}
			</ol>
		</div>
	</div>
{/if}

<style>
	.map {
		display: grid;
		grid-template-columns: 230px minmax(0, 1fr);
		gap: 1rem;
	}
	@media (max-width: 760px) {
		.map {
			grid-template-columns: minmax(0, 1fr);
		}
		.list {
			display: flex !important;
			overflow-x: auto;
		}
		.cl {
			min-width: 180px;
		}
	}
	.list {
		display: grid;
		gap: 0.3rem;
		align-content: start;
	}
	.cl {
		text-align: left;
		background: none;
		border: 1px solid transparent;
		border-radius: 8px;
		padding: 0.4rem 0.6rem;
		cursor: pointer;
		display: grid;
	}
	.cl:hover,
	.cl.on {
		background: var(--surface-1);
		border-color: var(--border);
	}
	.cl[aria-selected='true'] {
		border-color: var(--series-1);
	}
	.cl .nm {
		font-size: 0.85rem;
		color: var(--text-primary);
		font-weight: 550;
		line-height: 1.3;
	}
	.cl .meta {
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	.ttl {
		color: var(--text-muted);
	}
	.wrap {
		position: relative;
		margin: 0;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.family {
		transition: opacity 0.25s;
	}
	.family.off {
		opacity: 0.22;
	}
	.hull {
		fill: var(--surface-1);
		stroke: var(--border);
		stroke-width: 1;
	}
	.family.on .hull {
		stroke: var(--text-secondary);
		stroke-width: 1.5;
	}
	.game {
		cursor: pointer;
		transform-box: fill-box;
		transform-origin: center;
		transform: scale(0);
		transition: transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
	}
	.game.shown {
		transform: scale(1);
	}
	.game:hover {
		stroke: var(--text-primary);
		stroke-width: 2;
	}
	.label {
		font-size: 12px;
		font-weight: 600;
		fill: var(--text-secondary);
		paint-order: stroke;
		stroke: var(--page);
		stroke-width: 4px;
		stroke-linejoin: round;
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.5s 0.8s;
	}
	.label.shown {
		opacity: 1;
	}
	.label.shown.off {
		opacity: 0.25;
	}
	.detail {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 1.5rem;
		margin-top: 1rem;
	}
	@media (max-width: 760px) {
		.detail {
			grid-template-columns: minmax(0, 1fr);
		}
	}
	.trait {
		display: grid;
		grid-template-columns: minmax(0, 1.4fr) 1fr 3rem;
		gap: 0.6rem;
		align-items: center;
		font-size: 0.85rem;
		margin-bottom: 0.35rem;
	}
	.tn {
		color: var(--text-secondary);
	}
	.track {
		height: 8px;
		border-radius: 4px;
		background: var(--surface-2);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--series-1);
		border-radius: 4px;
		transition: width 0.5s;
	}
	.tv {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		text-align: right;
	}
	.tops {
		margin: 0;
		padding-left: 0;
		list-style: none;
	}
	.tops button {
		background: none;
		border: 0;
		padding: 0.2rem 0;
		cursor: pointer;
		color: var(--text-primary);
		font-size: 0.88rem;
		text-align: left;
	}
	.tops button:hover {
		text-decoration: underline;
	}
</style>
