<script lang="ts">
	import { tick } from 'svelte';
	import { fade, scale } from 'svelte/transition';
	import { prefersReducedMotion } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';
	import { data, fmt, kindLabel } from '#lib/data.ts';
	import { portal } from '#lib/portal.ts';
	import { chapters } from '#lib/chapters.ts';
	import {
		closeChapter,
		flyTo,
		openChapter,
		openGame,
		setGameOpener,
		toggleTheme,
		ui
	} from '#lib/state.svelte.ts';

	/**
	 * Where focus goes after an action: into the game drawer (and back to the opener when it
	 * closes), somewhere new that takes focus itself (a chapter, the map), or back to the opener.
	 */
	type Focus = 'drawer' | 'moves' | 'restore';
	type Action = { run: () => void; focus: Focus };
	type Item = Action & {
		id: string;
		group: 'Games' | 'Chapters' | 'Traits' | 'Actions';
		label: string;
		hint?: string;
		keywords?: string;
		/** Secondary action: Shift+Enter, or the pill on the row. */
		alt?: Action & { label: string };
	};

	let query = $state('');
	let active = $state(0);
	let input = $state<HTMLInputElement>();
	let trigger = $state<HTMLButtonElement>();
	let opener: HTMLElement | null = null;
	const isMac = $derived(
		typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
	);

	const top1000 = data.games.filter((g) => g.umap);
	const mostMagic = [...top1000].sort((a, b) => b.magic - a.magic)[0];

	const chapterItems: Item[] = [
		{
			id: 'home',
			group: 'Chapters',
			label: 'The 3D map',
			keywords: 'home start top space explore',
			focus: 'moves',
			run: closeChapter
		},
		{
			id: 'tour',
			group: 'Chapters',
			label: 'Take the guided tour',
			keywords: 'story walkthrough intro start',
			focus: 'moves',
			run: () => {
				closeChapter();
				ui.tour = true;
			}
		},
		...chapters.map((c, i) => ({
			id: `c-${c.id}`,
			group: 'Chapters' as const,
			label: c.label,
			hint: String(i + 1).padStart(2, '0'),
			keywords: c.title.toLowerCase(),
			focus: 'moves' as const,
			run: () => openChapter(c.id)
		}))
	];

	const actionItems: Item[] = $derived([
		{
			id: 'a-theme',
			group: 'Actions',
			label: `Switch to ${ui.theme === 'dark' ? 'light' : 'dark'} theme`,
			keywords: 'dark light mode colour color appearance',
			focus: 'restore',
			run: toggleTheme
		},
		{
			id: 'a-random',
			group: 'Actions',
			label: 'Fly to a random game',
			keywords: 'surprise shuffle lucky',
			focus: 'moves',
			run: () => flyTo(top1000[Math.floor(Math.random() * top1000.length)].id)
		},
		{
			id: 'a-magic',
			group: 'Actions',
			label: 'Fly to the game with the most magic sauce',
			keywords: 'overperformer best surprising',
			focus: 'moves',
			run: () => flyTo(mostMagic.id)
		},
		{
			id: 'a-source',
			group: 'Actions',
			label: 'View the source on GitHub',
			keywords: 'code repository',
			focus: 'restore',
			run: () =>
				window.open('https://github.com/nicholasjma/boardgameanalysis', '_blank', 'noopener')
		}
	]);

	// Games on the map fly there (details one keystroke away); the rest open their details.
	const gameItems: Item[] = data.games.map((g) => ({
		id: `g-${g.id}`,
		group: 'Games',
		label: g.name,
		hint: `#${g.rank} · ${g.year} · ${fmt.r2(g.rating)}`,
		...(g.umap
			? {
					focus: 'moves' as const,
					run: () => flyTo(g.id),
					alt: { label: 'Details', focus: 'drawer' as const, run: () => openGame(g.id) }
				}
			: { focus: 'drawer' as const, run: () => openGame(g.id) })
	}));

	// A trait lights up its games on the map; the explorer has the numbers.
	const traitItems: Item[] = data.traits.map((t) => ({
		id: `t-${t.key}`,
		group: 'Traits',
		label: t.name,
		hint: `${kindLabel[t.kind]} · ${t.count} games`,
		keywords: `${t.kind} trait`,
		focus: 'moves',
		run: () => {
			closeChapter();
			ui.tour = false;
			ui.scene = { mode: 'trait', trait: t.key, aimTrait: true, game: null, zoom: 2.2 };
		},
		alt: {
			label: 'Explorer',
			focus: 'moves',
			run: () => {
				ui.trait = t.key;
				openChapter('traits');
			}
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
		if (!q) return [...chapterItems, ...actionItems];
		const pick = (items: Item[], n: number) =>
			items
				.map((it, i) => ({ it, s: score(it, q), i }))
				.filter((x) => x.s >= 0)
				.sort((a, b) => b.s - a.s || a.i - b.i)
				.slice(0, n)
				.map((x) => x.it);
		return [
			...pick(gameItems, 7),
			...pick(chapterItems, 4),
			...pick(traitItems, 4),
			...pick(actionItems, 4)
		];
	});

	const groups = $derived(
		(['Games', 'Chapters', 'Traits', 'Actions'] as const)
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

	function run(item: Item, secondary = false) {
		const action = secondary && item.alt ? item.alt : item;
		if (action.focus === 'drawer') {
			// The drawer replaces the palette; when it closes, focus goes back to the opener.
			setGameOpener(opener ?? trigger ?? null);
			close(false);
		} else close(action.focus === 'restore');
		action.run();
	}

	const enterLabel = (item: Item | undefined) =>
		item?.group === 'Games' && item.alt
			? 'fly to it'
			: item?.group === 'Traits'
				? 'show on map'
				: 'open';

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
			run(flat[active], e.shiftKey);
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
					aria-label="Search games, chapters, traits and actions"
					aria-expanded="true"
					aria-controls="cmd-list"
					aria-autocomplete="list"
					aria-activedescendant={flat[active] ? `cmd-${flat[active].id}` : undefined}
					aria-describedby="cmd-help"
					placeholder="Search games, chapters, traits…"
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
									{#if item.alt}
										<!-- Pointer shortcut; keyboard users get Shift+Enter (see #cmd-help). -->
										<span
											class="map"
											aria-hidden="true"
											onclick={(e) => {
												e.stopPropagation();
												run(item, true);
											}}>{item.alt.label}</span
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
				<span><kbd>↵</kbd> {enterLabel(flat[active])}</span>
				{#if flat[active]?.alt}<span
						><kbd>⇧</kbd><kbd>↵</kbd> {flat[active].alt?.label.toLowerCase()}</span
					>{/if}
				<span><kbd>Esc</kbd> close</span>
			</div>
			<p id="cmd-help" class="visually-hidden">
				Enter flies the 3D map to a game or lights up a trait on it. Shift+Enter opens a game’s
				details, or the trait explorer.
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
