<script lang="ts">
	import { data } from '#lib/data.ts';
	import { openGame, ui } from '#lib/state.svelte.ts';

	let q = $state('');
	let open = $state(false);
	let active = $state(0);

	const results = $derived.by(() => {
		const s = q.trim().toLowerCase();
		if (s.length < 2) return [];
		const starts = data.games.filter((g) => g.name.toLowerCase().startsWith(s));
		const has = data.games.filter(
			(g) => !g.name.toLowerCase().startsWith(s) && g.name.toLowerCase().includes(s)
		);
		return [...starts, ...has].slice(0, 8);
	});

	function choose(id: number) {
		openGame(id);
		q = '';
		open = false;
		ui.hoverGame = null;
	}

	function onKey(e: KeyboardEvent) {
		if (!results.length) return;
		if (e.key === 'ArrowDown') {
			active = (active + 1) % results.length;
			e.preventDefault();
		} else if (e.key === 'ArrowUp') {
			active = (active - 1 + results.length) % results.length;
			e.preventDefault();
		} else if (e.key === 'Enter') {
			choose(results[active].id);
		} else if (e.key === 'Escape') {
			open = false;
		}
	}

	// Highlight the candidate on the scatter while browsing results.
	$effect(() => {
		ui.hoverGame = open && results.length ? (results[active]?.id ?? null) : null;
	});
</script>

<div class="search">
	<label for="game-search" class="visually-hidden">Find a game</label>
	<input
		id="game-search"
		type="search"
		placeholder="Find a game…"
		autocomplete="off"
		role="combobox"
		aria-expanded={open && results.length > 0}
		aria-controls="game-search-list"
		aria-activedescendant={results.length ? `gs-${results[active]?.id}` : undefined}
		bind:value={q}
		oninput={() => {
			open = true;
			active = 0;
		}}
		onfocus={() => (open = true)}
		onblur={() => setTimeout(() => (open = false), 150)}
		onkeydown={onKey}
	/>
	{#if open && results.length}
		<ul id="game-search-list" role="listbox">
			{#each results as g, i (g.id)}
				<li id="gs-{g.id}" role="option" aria-selected={i === active}>
					<button tabindex="-1" onmousedown={() => choose(g.id)} onmouseenter={() => (active = i)}>
						<span class="nm">{g.name}</span>
						<span class="meta">#{g.rank} · {g.year}</span>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.search {
		position: relative;
		width: min(320px, 46vw);
	}
	input {
		width: 100%;
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 999px;
		padding: 0.4rem 0.9rem;
		font-size: 0.88rem;
	}
	ul {
		position: absolute;
		top: calc(100% + 6px);
		left: 0;
		right: 0;
		margin: 0;
		padding: 0.3rem;
		list-style: none;
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: var(--shadow);
		z-index: 30;
	}
	button {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		width: 100%;
		background: none;
		border: 0;
		border-radius: 6px;
		padding: 0.4rem 0.55rem;
		cursor: pointer;
		text-align: left;
		font-size: 0.86rem;
	}
	li[aria-selected='true'] button {
		background: var(--surface-2);
	}
	.nm {
		color: var(--text-primary);
	}
	.meta {
		color: var(--text-muted);
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
</style>
