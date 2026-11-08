<script lang="ts">
	import { tick } from 'svelte';
	import { chapterById, chapterHref, chapters } from '#lib/chapters.ts';
	import { closeChapter, openChapter, ui } from '#lib/state.svelte.ts';

	// One menu for every screen width: a row of nine links never fit a phone, and on mid-size
	// screens it ran off the edge.
	let open = $state(false);
	let root = $state<HTMLElement>();
	let btn = $state<HTMLButtonElement>();
	let list = $state<HTMLElement>();
	const current = $derived(ui.pane && !ui.paneHidden ? chapterById.get(ui.pane) : undefined);
	const links = () => [...(list?.querySelectorAll<HTMLElement>('a, button') ?? [])];

	async function toggle() {
		open = !open;
		if (!open) return;
		await tick();
		(list?.querySelector<HTMLElement>('[aria-current]') ?? links()[0])?.focus();
	}
	function shut(refocus = true) {
		open = false;
		if (refocus) btn?.focus();
	}
	function go(e: MouseEvent, id: string) {
		e.preventDefault();
		shut(false);
		if (id) openChapter(id, btn ?? null);
		else {
			closeChapter();
			btn?.focus();
		}
	}
	function tour() {
		shut(false);
		closeChapter();
		ui.tour = true;
	}
	function onKey(e: KeyboardEvent) {
		if (!open) return;
		const items = links();
		const at = items.indexOf(document.activeElement as HTMLElement);
		if (e.key === 'Escape') {
			e.preventDefault();
			e.stopPropagation();
			shut();
		} else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			e.preventDefault();
			const n = items.length;
			items[(at + (e.key === 'ArrowDown' ? 1 : -1) + n) % n]?.focus();
		} else if (e.key === 'Home' || e.key === 'End') {
			e.preventDefault();
			items[e.key === 'Home' ? 0 : items.length - 1]?.focus();
		}
	}
	function onOutside(e: PointerEvent) {
		if (open && root && !root.contains(e.target as Node)) shut(false);
	}
</script>

<svelte:window onpointerdown={onOutside} />

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<nav class="menu" aria-label="Chapters" bind:this={root} onkeydown={onKey}>
	<button
		class="toggle"
		bind:this={btn}
		aria-expanded={open}
		aria-controls="chapter-list"
		onclick={toggle}
	>
		<span>Chapters</span>{#if current}<span class="cur">: {current.label}</span>{/if}
		<svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"
			><path d="m2 4 4 4 4-4" /></svg
		>
	</button>
	{#if open}
		<ol id="chapter-list" bind:this={list}>
			<li>
				<a href="./" aria-current={!current ? 'page' : undefined} onclick={(e) => go(e, '')}
					><span class="n" aria-hidden="true">◎</span>The 3D map</a
				>
			</li>
			<li>
				<button onclick={tour}><span class="n" aria-hidden="true">▶</span>Guided tour</button>
			</li>
			{#each chapters as c, i (c.id)}
				<li>
					<a
						href={chapterHref(c.id)}
						aria-current={current?.id === c.id ? 'page' : undefined}
						onclick={(e) => go(e, c.id)}
						><span class="n">{String(i + 1).padStart(2, '0')}</span>{c.label}</a
					>
				</li>
			{/each}
		</ol>
	{/if}
</nav>

<style>
	.menu {
		position: relative;
		min-width: 0;
	}
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		max-width: 100%;
		min-height: 36px;
		padding: 0.3rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 999px;
		background: var(--surface-1);
		color: var(--text-primary);
		font-size: 0.85rem;
		cursor: pointer;
		white-space: nowrap;
	}
	.cur {
		overflow: hidden;
		text-overflow: ellipsis;
		color: var(--text-secondary);
	}
	@media (max-width: 640px) {
		.cur {
			display: none;
		}
	}
	svg path {
		fill: none;
		stroke: currentColor;
		stroke-width: 1.6;
	}
	ol {
		position: absolute;
		top: calc(100% + 0.4rem);
		left: 0;
		z-index: 30;
		min-width: 240px;
		margin: 0;
		padding: 0.35rem;
		list-style: none;
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 12px;
		box-shadow: var(--shadow);
	}
	li a,
	li button {
		display: flex;
		gap: 0.6rem;
		width: 100%;
		padding: 0.4rem 0.55rem;
		border: 0;
		border-radius: 8px;
		background: none;
		color: var(--text-primary);
		font-size: 0.9rem;
		text-align: left;
		text-decoration: none;
		cursor: pointer;
	}
	li a:hover,
	li button:hover,
	li a:focus-visible,
	li button:focus-visible {
		background: var(--surface-2);
	}
	li a[aria-current] {
		box-shadow: inset 3px 0 0 var(--series-1);
		font-weight: 600;
	}
	.n {
		width: 1.4rem;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
</style>
