<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { prefersReducedMotion } from 'svelte/motion';
	import { bggUrl, data, fmt, gamesById } from '#lib/data.ts';
	import { closeGame, goToSection, ui } from '#lib/state.svelte.ts';
	import Waterfall from '#lib/charts/Waterfall.svelte';

	const game = $derived(ui.game === null ? null : (gamesById.get(ui.game) ?? null));
	const total = $derived(game?.dist ? game.dist.reduce((a, b) => a + b, 0) : 0);
	const maxDist = $derived(game?.dist ? Math.max(...game.dist) : 1);
	const traitNames = $derived(game ? game.traits.map((i) => data.traits[i]) : []);

	let panel = $state<HTMLElement | null>(null);
	$effect(() => {
		if (game && panel) panel.focus();
	});

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && ui.game !== null && !ui.palette) closeGame();
	}

	/** Modal: keep Tab and Shift+Tab cycling inside the drawer. */
	function trap(e: KeyboardEvent) {
		if (e.key !== 'Tab' || !panel) return;
		const items = [
			...panel.querySelectorAll<HTMLElement>('a[href], button, [tabindex="0"], summary')
		].filter((el) => el.getClientRects().length);
		if (!items.length) return;
		const [first, last] = [items[0], items[items.length - 1]];
		const here = document.activeElement;
		if (e.shiftKey && (here === first || here === panel)) {
			e.preventDefault();
			last.focus();
		} else if (!e.shiftKey && here === last) {
			e.preventDefault();
			first.focus();
		}
	}

	function showOnMap(id: number) {
		closeGame();
		setTimeout(() => {
			ui.mapGame = id;
			goToSection('space');
		});
	}

	function pickTrait(key: string) {
		ui.trait = key;
		closeGame();
		setTimeout(() => goToSection('traits'));
	}

	const dur = (ms: number) => (prefersReducedMotion.current ? 0 : ms);
</script>

<svelte:window onkeydown={onKey} />

{#if game}
	<button
		class="scrim"
		tabindex="-1"
		aria-label="Close details"
		onclick={closeGame}
		transition:fade={{ duration: dur(180) }}
	></button>
	<div
		class="drawer"
		role="dialog"
		aria-modal="true"
		aria-labelledby="drawer-title"
		tabindex="-1"
		bind:this={panel}
		onkeydown={trap}
		transition:fly={{ x: 420, duration: dur(320), easing: cubicOut }}
	>
		<div class="head">
			<div>
				<p class="eyebrow">#{game.rank} on BoardGameGeek · {game.year}</p>
				<h2 id="drawer-title">{game.name}</h2>
			</div>
			<button class="close" onclick={closeGame} aria-label="Close details">×</button>
		</div>

		<div class="kpis">
			<div><span class="k">Actual</span><span class="n">{fmt.r2(game.rating)}</span></div>
			<div><span class="k">Predicted</span><span class="n">{fmt.r2(game.pred)}</span></div>
			<div>
				<span class="k">Magic sauce</span>
				<span class="n" class:pos={game.magic >= 0} class:neg={game.magic < 0}
					>{fmt.signed(game.magic)}</span
				>
			</div>
		</div>

		<dl class="facts">
			<div>
				<dt>Ratings</dt>
				<dd>{fmt.int(game.votes)}</dd>
			</div>
			<div>
				<dt>Players</dt>
				<dd>{game.players[0]}–{game.players[1]}</dd>
			</div>
			<div>
				<dt>Play time</dt>
				<dd>{game.time} min</dd>
			</div>
			<div>
				<dt>Weight</dt>
				<dd>{game.weight === null ? '—' : `${fmt.r2(game.weight)} / 5`}</dd>
			</div>
			{#if game.wish}<div>
					<dt>Wishlisted</dt>
					<dd>{fmt.int(game.wish)}</dd>
				</div>{/if}
			{#if game.then}
				<div>
					<dt>In {data.compare?.snapshot.slice(0, 4)}</dt>
					<dd>#{fmt.int(game.then.rank)} · {fmt.r2(game.then.rating)}</dd>
				</div>
			{/if}
		</dl>

		<section>
			<h3>Why the model predicts {fmt.r2(game.pred)}</h3>
			<p class="sub">
				Each bar is one feature's contribution (SHAP), from a model that never saw this game.
			</p>
			{#key game.id}<Waterfall {game} />{/key}
		</section>

		{#if game.dist}
			<section>
				<h3>How {fmt.compact(total)} people rated it</h3>
				<div class="dist" role="img" aria-label="Distribution of ratings from 1 to 10">
					{#each game.dist as n, i (i)}
						<div class="col">
							<div class="barwrap">
								<div
									class="b"
									style:height="{(n / maxDist) * 100}%"
									style:animation-delay="{i * 35}ms"
									title="{fmt.int(n)} ratings of {i + 1}"
								></div>
							</div>
							<span class="x">{i + 1}</span>
						</div>
					{/each}
				</div>
				<p class="sub">
					{fmt.pct(game.dist.slice(8).reduce((a, b) => a + b, 0) / total)} gave it a 9 or 10 ·
					{fmt.pct(game.dist.slice(0, 5).reduce((a, b) => a + b, 0) / total)} gave it 5 or less
				</p>
			</section>
		{/if}

		<section>
			<h3>Traits</h3>
			<div class="chips">
				{#each traitNames as t (t.key)}
					<button class="chip" onclick={() => pickTrait(t.key)} title="Explore {t.name}"
						>{t.name}</button
					>
				{/each}
			</div>
		</section>

		<div class="outs">
			{#if game.umap}
				<button class="chip" onclick={() => showOnMap(game.id)}
					>Show similar games on the 3D map</button
				>
			{/if}
			<a class="out" href={bggUrl(game.id)} target="_blank" rel="noopener"
				>View on BoardGameGeek ↗</a
			>
		</div>
	</div>
{/if}

<style>
	.scrim {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.35);
		border: 0;
		z-index: 40;
		cursor: pointer;
	}
	.drawer {
		position: fixed;
		top: 0;
		right: 0;
		height: 100dvh;
		width: min(480px, 100vw);
		background: var(--page);
		border-left: 1px solid var(--border);
		box-shadow: var(--shadow);
		z-index: 50;
		overflow-y: auto;
		padding: 1.25rem 1.4rem 2rem;
		outline: none;
	}
	.head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}
	h2 {
		font-size: 1.6rem;
		margin: 0;
	}
	.close {
		background: none;
		border: 0;
		font-size: 1.8rem;
		line-height: 1;
		cursor: pointer;
		color: var(--text-muted);
		align-self: start;
		min-width: 36px;
		min-height: 36px;
		border-radius: 8px;
	}
	.kpis {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.6rem;
		margin: 1rem 0;
	}
	.kpis > div {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 0.6rem 0.75rem;
		display: grid;
	}
	.k {
		font-size: 0.75rem;
		color: var(--text-secondary);
	}
	.n {
		font-size: 1.5rem;
		font-weight: 650;
	}
	.n.pos {
		color: var(--div-pos);
	}
	.n.neg {
		color: var(--div-neg);
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0.5rem 1rem;
		margin: 0 0 1.25rem;
		font-size: 0.85rem;
	}
	dt {
		color: var(--text-muted);
		font-size: 0.75rem;
	}
	dd {
		margin: 0;
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
	}
	section {
		border-top: 1px solid var(--grid);
		padding-top: 1rem;
		margin-top: 1rem;
	}
	.sub {
		font-size: 0.8rem;
		color: var(--text-muted);
		margin: 0 0 0.6rem;
	}
	.dist {
		display: grid;
		grid-template-columns: repeat(10, 1fr);
		gap: 4px;
		height: 130px;
		margin-bottom: 0.5rem;
	}
	.col {
		display: grid;
		grid-template-rows: 1fr auto;
		gap: 4px;
	}
	.barwrap {
		display: flex;
		align-items: flex-end;
	}
	.b {
		width: 100%;
		max-width: 24px;
		margin: 0 auto;
		background: var(--series-1);
		border-radius: 4px 4px 0 0;
		animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
		transform-origin: bottom;
	}
	@keyframes rise {
		from {
			transform: scaleY(0);
		}
	}
	.x {
		text-align: center;
		font-size: 0.72rem;
		color: var(--text-muted);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.outs {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1rem;
		margin-top: 1.5rem;
	}
	.out {
		display: inline-block;
		font-weight: 600;
	}
</style>
