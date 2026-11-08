<script lang="ts">
	import { tick } from 'svelte';
	import { fade, scale } from 'svelte/transition';
	import { prefersReducedMotion } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';
	import { data, fmt, kindLabel } from '#lib/data.ts';
	import { portal } from '#lib/portal.ts';
	import { goToSection, openGame, setGameOpener, toggleTheme, ui } from '#lib/state.svelte.ts';

	let { sections }: { sections: readonly (readonly [string, string])[] } = $props();

	type Item = {
		id: string;
		group: 'Games' | 'Sections' | 'Traits' | 'Actions';
		label: string;
		hint?: string;
		keywords?: string;
		run: () => void;
		/** Secondary action (Shift+Enter, or the row's pill): show the game on the 3D map. */
		onMap?: () => void;
	};

	let query = $state('');
	let active = $state(0);
	let input = $state<HTMLInputElement>();
	let trigger = $state<HTMLButtonElement>();
	let opener: HTMLElement | null = null;
	const isMac = $derived(
		typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
	);

	const sectionItems: Item[] = $derived([
		{
			id: 's-top',
			group: 'Sections',
			label: 'Top of page',
			keywords: 'home start hero',
			run: () => goToSection('top')
		},
		...sections.map(([id, label]) => ({
			id: `s-${id}`,
			group: 'Sections' as const,
			label,
			run: () => goToSection(id)
		})),
		{
			id: 's-methods',
			group: 'Sections',
			label: 'Methods & data',
			keywords: 'about source license',
			run: () => goToSection('methods')
		}
	]);

	const actionItems: Item[] = $derived([
		{
			id: 'a-theme',
			group: 'Actions',
			label: `Switch to ${ui.theme === 'dark' ? 'light' : 'dark'} theme`,
			keywords: 'dark light mode colour color appearance',
			run: toggleTheme
		},
		{
			id: 'a-random',
			group: 'Actions',
			label: 'Open a random top-500 game',
			keywords: 'surprise shuffle lucky',
			run: () => openGame(data.games[Math.floor(Math.random() * 500)].id)
		},
		{
			id: 'a-magic',
			group: 'Actions',
			label: 'Open the game with the most magic sauce',
			keywords: 'overperformer best surprising',
			run: () => openGame([...data.games].sort((a, b) => b.magic - a.magic)[0].id)
		},
		{
			id: 'a-source',
			group: 'Actions',
			label: 'View the source on GitHub',
			keywords: 'code repository',
			run: () =>
				window.open('https://github.com/nicholasjma/boardgameanalysis', '_blank', 'noopener')
		}
	]);

	const gameItems: Item[] = data.games.map((g) => ({
		id: `g-${g.id}`,
		group: 'Games',
		label: g.name,
		hint: `#${g.rank} · ${g.year} · ${fmt.r2(g.rating)}`,
		run: () => openGame(g.id),
		onMap: g.umap
			? () => {
					ui.mapGame = g.id;
					goToSection('space');
				}
			: undefined
	}));

	const traitItems: Item[] = data.traits.map((t) => ({
		id: `t-${t.key}`,
		group: 'Traits',
		label: `Explore ${t.name}`,
		hint: `${kindLabel[t.kind]} · ${t.count} games`,
		keywords: t.kind,
		run: () => {
			ui.trait = t.key;
			goToSection('traits');
		}
	}));

	/** Rank by where the query matches: whole label, word start, then anywhere. */
	function score(item: Item, q: string): number {
		const label = item.label.toLowerCase();
		const hay = `${label} ${item.keywords ?? ''}`;
		const words = q.split(/\s+/).filter(Boolean);
		if (!words.every((w) => hay.includes(w))) return -1;
		if (label.startsWith(q)) return 3;
		if (label.includes(` ${q}`)) return 2;
		return 1;
	}

	const results = $derived.by((): Item[] => {
		const q = query.trim().toLowerCase();
		if (!q) return [...sectionItems, ...actionItems];
		const pick = (items: Item[], n: number) =>
			items
				.map((it, i) => ({ it, s: score(it, q), i }))
				.filter((x) => x.s >= 0)
				.sort((a, b) => b.s - a.s || a.i - b.i)
				.slice(0, n)
				.map((x) => x.it);
		return [
			...pick(gameItems, 7),
			...pick(sectionItems, 4),
			...pick(traitItems, 4),
			...pick(actionItems, 4)
		];
	});

	const groups = $derived(
		(['Games', 'Sections', 'Traits', 'Actions'] as const)
			.map((g) => ({ name: g, items: results.filter((r) => r.group === g) }))
			.filter((g) => g.items.length)
	);
	// Flat order for arrow keys, matching the grouped render order.
	const flat = $derived(groups.flatMap((g) => g.items));

	$effect(() => {
		void query;
		active = 0;
	});

	async function open() {
		if (ui.palette) return;
		opener = document.activeElement instanceof HTMLElement ? document.activeElement : trigger!;
		query = '';
		ui.palette = true;
		await tick();
		input?.focus();
	}

	function close(restore = true) {
		ui.palette = false;
		if (restore) (opener ?? trigger)?.focus({ preventScroll: true });
	}

	function run(item: Item) {
		// A game drawer replaces the palette; when it closes, focus goes back to the opener.
		if (item.group === 'Games' || item.id === 'a-random' || item.id === 'a-magic') {
			setGameOpener(opener ?? trigger ?? null);
			close(false);
		} else if (item.group === 'Sections' || item.group === 'Traits') {
			close(false); // focus moves to the section heading
		} else {
			close();
		}
		item.run();
	}

	function showOnMap(item: Item) {
		close(false); // focus moves to the map section's heading
		item.onMap?.();
	}

	function onWindowKey(e: KeyboardEvent) {
		const typing =
			e.target instanceof HTMLElement &&
			(e.target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName));
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
			e.preventDefault();
			if (ui.palette) close();
			else open();
		} else if (e.key === '/' && !typing && !ui.palette && ui.game === null) {
			e.preventDefault();
			open();
		}
	}

	function onKey(e: KeyboardEvent) {
		const n = flat.length;
		if (e.key === 'ArrowDown' && n) {
			e.preventDefault();
			active = (active + 1) % n;
		} else if (e.key === 'ArrowUp' && n) {
			e.preventDefault();
			active = (active - 1 + n) % n;
		} else if (e.key === 'Home' && n && !query) {
			e.preventDefault();
			active = 0;
		} else if (e.key === 'End' && n && !query) {
			e.preventDefault();
			active = n - 1;
		} else if (e.key === 'Enter' && flat[active]) {
			e.preventDefault();
			if (e.shiftKey && flat[active].onMap) showOnMap(flat[active]);
			else run(flat[active]);
		} else if (e.key === 'Escape') {
			e.preventDefault();
			e.stopPropagation();
			close();
		} else if (e.key === 'Tab') {
			e.preventDefault(); // the input is the only stop in this modal
		}
	}

	// Keep the active option scrolled into view.
	$effect(() => {
		const id = flat[active]?.id;
		if (id && ui.palette)
			document.getElementById(`cmd-${id}`)?.scrollIntoView({ block: 'nearest', behavior: 'auto' });
	});

	const dur = (ms: number) => (prefersReducedMotion.current ? 0 : ms);
	const status = $derived(
		query.trim() ? `${flat.length} result${flat.length === 1 ? '' : 's'}` : ''
	);
</script>

<svelte:window onkeydown={onWindowKey} />

<button
	class="trigger"
	bind:this={trigger}
	onclick={open}
	aria-haspopup="dialog"
	aria-keyshortcuts="Control+K Meta+K /"
>
	<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
		<circle cx="11" cy="11" r="7" />
		<path d="m20 20-3.5-3.5" />
	</svg>
	<span class="ph">Find a game…</span>
	<kbd>{isMac ? '⌘' : 'Ctrl'} K</kbd>
	<span class="visually-hidden">(search and commands)</span>
</button>

{#if ui.palette}
	<div class="backdrop" use:portal transition:fade={{ duration: dur(140) }} data-palette>
		<button class="scrim" tabindex="-1" aria-label="Close command menu" onclick={() => close()}
		></button>
		<div
			class="panel"
			role="dialog"
			aria-modal="true"
			aria-label="Command menu"
			transition:scale={{ start: 0.97, duration: dur(180), easing: cubicOut }}
		>
			<div class="search">
				<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
					<circle cx="11" cy="11" r="7" />
					<path d="m20 20-3.5-3.5" />
				</svg>
				<input
					bind:this={input}
					bind:value={query}
					onkeydown={onKey}
					type="text"
					role="combobox"
					aria-label="Search games, sections, traits and actions"
					aria-expanded="true"
					aria-controls="cmd-list"
					aria-autocomplete="list"
					aria-activedescendant={flat[active] ? `cmd-${flat[active].id}` : undefined}
					aria-describedby="cmd-help"
					placeholder="Search games, sections, traits…"
					autocomplete="off"
					spellcheck="false"
				/>
				<kbd aria-hidden="true">Esc</kbd>
			</div>
			<div id="cmd-list" role="listbox" aria-label="Results" class="list">
				{#each groups as g, gi (g.name)}
					<div role="group" aria-labelledby="cmd-h-{gi}">
						<div class="group" id="cmd-h-{gi}" role="presentation">
							{g.name}
						</div>
						{#each g.items as item (item.id)}
							{@const i = flat.indexOf(item)}
							<!-- svelte-ignore a11y_click_events_have_key_events -->
							<div
								id="cmd-{item.id}"
								class="opt"
								role="option"
								tabindex="-1"
								aria-selected={i === active}
								onpointermove={() => (active = i)}
								onclick={() => run(item)}
							>
								<span class="label">{item.label}</span>
								<span class="right">
									{#if item.hint}<span class="hint">{item.hint}</span>{/if}
									{#if item.onMap}
										<!-- Pointer shortcut; keyboard users get Shift+Enter (see #cmd-help). -->
										<span
											class="map"
											aria-hidden="true"
											title="Show {item.label} and similar games on the 3D map"
											onclick={(e) => {
												e.stopPropagation();
												showOnMap(item);
											}}>3D map</span
										>
									{/if}
								</span>
							</div>
						{/each}
					</div>
				{:else}
					<p class="empty">No matches for “{query}”</p>
				{/each}
			</div>
			<div class="foot" aria-hidden="true">
				<span><kbd>↑</kbd><kbd>↓</kbd> move</span>
				<span><kbd>↵</kbd> open</span>
				{#if flat[active]?.onMap}<span><kbd>⇧</kbd><kbd>↵</kbd> show on 3D map</span>{/if}
				<span><kbd>Esc</kbd> close</span>
			</div>
			<p id="cmd-help" class="visually-hidden">
				Enter opens the result. For a game in the top 1,000, Shift+Enter shows it and similar games
				on the 3D map.
			</p>
			<div class="visually-hidden" role="status" aria-live="polite">{status}</div>
		</div>
	</div>
{/if}

<style>
	.trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		height: 36px;
		min-width: 36px;
		padding: 0 0.5rem 0 0.75rem;
		border: 1px solid var(--border);
		border-radius: 999px;
		background: var(--surface-1);
		color: var(--text-muted);
		font-size: 0.85rem;
		cursor: pointer;
	}
	.trigger:hover {
		color: var(--text-secondary);
	}
	.trigger svg,
	.search svg {
		fill: none;
		stroke: currentColor;
		stroke-width: 2;
		stroke-linecap: round;
		flex: none;
	}
	.ph {
		min-width: 9rem;
		text-align: left;
	}
	kbd {
		font: inherit;
		font-size: 0.72rem;
		line-height: 1;
		padding: 0.2rem 0.35rem;
		border: 1px solid var(--border);
		border-radius: 5px;
		background: var(--surface-2);
		color: var(--text-secondary);
	}
	@media (max-width: 640px) {
		.trigger {
			padding: 0;
			justify-content: center;
			width: 36px;
		}
		.ph,
		.trigger kbd {
			display: none;
		}
	}

	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 60;
		display: grid;
		justify-items: center;
		align-items: start;
		padding: 12vh 1rem 1rem;
	}
	.scrim {
		position: absolute;
		inset: 0;
		border: 0;
		background: color-mix(in srgb, var(--page) 60%, transparent);
		backdrop-filter: blur(4px);
		cursor: default;
	}
	.panel {
		position: relative;
		width: min(620px, 100%);
		max-height: 76vh;
		display: flex;
		flex-direction: column;
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 14px;
		box-shadow:
			0 24px 64px rgba(0, 0, 0, 0.25),
			0 2px 6px rgba(0, 0, 0, 0.08);
		overflow: hidden;
	}
	.search {
		display: flex;
		align-items: center;
		gap: 0.65rem;
		padding: 0.85rem 1rem;
		border-bottom: 1px solid var(--border);
		color: var(--text-muted);
	}
	input {
		flex: 1;
		min-width: 0;
		border: 0;
		background: none;
		font-size: 1rem;
		color: var(--text-primary);
	}
	input:focus-visible {
		outline: none; /* the panel shows focus: it is the only control */
	}
	.panel:focus-within {
		outline: 2px solid var(--series-1);
		outline-offset: -1px;
	}
	input::placeholder {
		color: var(--text-muted);
		opacity: 1;
	}
	.list {
		overflow-y: auto;
		padding: 0.35rem;
		overscroll-behavior: contain;
	}
	.group {
		font-size: 0.72rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
		padding: 0.6rem 0.65rem 0.3rem;
	}
	.opt {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
		min-height: 36px;
		padding: 0.45rem 0.65rem;
		border-radius: 8px;
		cursor: pointer;
		color: var(--text-primary);
		font-size: 0.92rem;
	}
	.opt[aria-selected='true'] {
		background: var(--surface-2);
		box-shadow: inset 3px 0 0 var(--series-1);
	}
	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.right {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		flex: none;
	}
	.map {
		font-size: 0.72rem;
		font-weight: 600;
		padding: 0.15rem 0.45rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		color: var(--text-secondary);
		background: var(--surface-1);
		cursor: pointer;
		visibility: hidden;
	}
	.opt[aria-selected='true'] .map {
		visibility: visible;
	}
	.map:hover {
		color: var(--text-primary);
		border-color: var(--series-1);
	}
	@media (hover: none) {
		.map {
			visibility: visible;
		}
	}
	.hint {
		flex: none;
		font-size: 0.78rem;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.empty {
		padding: 1.25rem;
		text-align: center;
		color: var(--text-muted);
		margin: 0;
	}
	.foot {
		display: flex;
		gap: 1rem;
		padding: 0.5rem 1rem;
		border-top: 1px solid var(--border);
		font-size: 0.75rem;
		color: var(--text-muted);
	}
	.foot kbd {
		margin-right: 0.2rem;
	}
	@media (max-width: 640px) {
		.foot {
			display: none;
		}
	}
</style>
