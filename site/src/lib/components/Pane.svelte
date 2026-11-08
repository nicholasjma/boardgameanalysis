<script lang="ts">
	import { tick, type Snippet } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { prefersReducedMotion } from 'svelte/motion';
	import { chapterHref, chapters } from '#lib/chapters.ts';
	import { closeChapter, openChapter, ui } from '#lib/state.svelte.ts';

	let { children }: { children: Snippet } = $props();

	// A chapter slides over the map. Prev / next walk the whole story; Escape, the map button or a
	// click on the strip of map still showing goes back to the map.
	const at = $derived(chapters.findIndex((c) => c.id === ui.pane));
	const ch = $derived(chapters[at]);
	const prev = $derived(chapters[at - 1]);
	const next = $derived(chapters[at + 1]);
	let body = $state<HTMLElement>();
	let head = $state<HTMLElement>();

	// A new chapter starts at the top with its heading focused.
	$effect(() => {
		void ui.pane;
		tick().then(() => {
			if (body) body.scrollTop = 0;
			head?.focus({ preventScroll: true });
		});
	});

	function onKey(e: KeyboardEvent) {
		if (e.key !== 'Escape' || e.defaultPrevented) return;
		if (ui.pane === null || ui.paneHidden || ui.game !== null || ui.palette) return;
		e.preventDefault();
		closeChapter();
	}
	const go = (id: string, e: MouseEvent) => {
		e.preventDefault();
		openChapter(id, e.currentTarget as HTMLElement);
	};
	const dur = (ms: number) => (prefersReducedMotion.current ? 0 : ms);
</script>

<svelte:window onkeydown={onKey} />

{#if ch}
	<div class="wrap" hidden={ui.paneHidden} data-pane>
		<button
			class="scrim"
			tabindex="-1"
			aria-label="Back to the map"
			onclick={closeChapter}
			transition:fade={{ duration: dur(160) }}
		></button>
		<section
			class="pane"
			aria-labelledby="pane-title"
			bind:this={body}
			transition:fly={{ x: 80, duration: dur(260), easing: cubicOut }}
		>
			<div class="bar">
				<button class="chip map" onclick={closeChapter}>← 3D map</button>
				<p class="where">
					<span class="num">{String(at + 1).padStart(2, '0')} / {chapters.length}</span>
					{ch.label}
				</p>
				<nav class="step" aria-label="Previous and next chapter">
					{#if prev}
						<a class="chip" href={chapterHref(prev.id)} onclick={(e) => go(prev.id, e)}
							>← <span class="visually-hidden">Previous: </span>{prev.label}</a
						>
					{/if}
					{#if next}
						<a class="chip" href={chapterHref(next.id)} onclick={(e) => go(next.id, e)}
							><span class="visually-hidden">Next: </span>{next.label} →</a
						>
					{/if}
				</nav>
			</div>
			<div class="body">
				<h2 id="pane-title" tabindex="-1" bind:this={head}>{ch.title}</h2>
				{#key ch.id}
					{@render children()}
				{/key}
				<div class="foot">
					{#if next}
						<a class="nextcard" href={chapterHref(next.id)} onclick={(e) => go(next.id, e)}>
							<span class="k">Next · {String(at + 2).padStart(2, '0')}</span>
							<span class="t">{next.label}: {next.title}</span>
						</a>
					{/if}
					<button class="chip" onclick={closeChapter}>Back to the 3D map</button>
				</div>
			</div>
		</section>
	</div>
{/if}

<style>
	.wrap {
		position: fixed;
		inset: 56px 0 0 0;
		z-index: 15;
	}
	.wrap[hidden] {
		display: none;
	}
	.scrim {
		position: absolute;
		inset: 0;
		width: 100%;
		border: 0;
		padding: 0;
		background: color-mix(in srgb, var(--page) 45%, transparent);
		cursor: pointer;
	}
	.pane {
		position: absolute;
		top: 0;
		right: 0;
		bottom: 0;
		width: min(1120px, calc(100vw - 4.5rem));
		overflow-y: auto;
		background: var(--page);
		border-left: 1px solid var(--border);
		box-shadow: var(--shadow);
		overscroll-behavior: contain;
	}
	@media (max-width: 700px) {
		.pane {
			width: 100%;
			border-left: 0;
		}
	}
	.bar {
		position: sticky;
		top: 0;
		z-index: 2;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.9rem;
		padding: 0.6rem 1.25rem;
		background: color-mix(in srgb, var(--page) 92%, transparent);
		backdrop-filter: blur(8px);
		border-bottom: 1px solid var(--border);
	}
	.where {
		margin: 0;
		font-size: 0.85rem;
		color: var(--text-secondary);
	}
	.num {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
		margin-right: 0.35rem;
	}
	.step {
		display: flex;
		gap: 0.35rem;
		margin-left: auto;
	}
	.step a {
		text-decoration: none;
	}
	.body {
		padding: 1.5rem 1.25rem 3rem;
	}
	h2 {
		font-size: clamp(1.6rem, 3.4vw, 2.4rem);
		letter-spacing: -0.02em;
		margin: 0 0 1rem;
	}
	.foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem;
		margin-top: 3rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--grid);
	}
	.nextcard {
		display: grid;
		gap: 0.2rem;
		padding: 0.8rem 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--surface-1);
		text-decoration: none;
		max-width: 520px;
	}
	.nextcard:hover {
		border-color: var(--series-1);
	}
	.nextcard .k {
		color: var(--text-muted);
		font-size: 0.78rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
	}
	.nextcard .t {
		color: var(--text-primary);
		font-weight: 600;
	}
</style>
