<script lang="ts">
	import { onMount } from 'svelte';
	import { data, fmt } from '#lib/data.ts';
	import { chapterById } from '#lib/chapters.ts';
	import { openChapter, scrollBehavior, ui, type Scene } from '#lib/state.svelte.ts';
	import { pts, regions, traitIndex } from '#lib/space.ts';

	let { onexit }: { onexit: () => void } = $props();

	// Semantic scroll: scrolling through the story moves the map. Each step names the view it
	// wants; whichever step crosses the middle of the panel sets the scene.
	type Step = { title: string; body: string; scene: Scene; chapter?: string };

	const n = pts.length;
	const top = data.games[0];
	const topMagic = [...data.games]
		.filter((g) => g.rank <= 100)
		.sort((a, b) => b.magic - a.magic)[0];
	const yearsTop = data.importance.findIndex((i) => i.feature === 'Year published') + 1;
	const count = (key: string) => {
		const bit = traitIndex.get(key) ?? -1;
		return pts.filter((d) => d.g.traits.includes(bit)).length;
	};
	const ordinal = (k: number) =>
		k === 1 ? 'top' : k === 2 ? 'second' : k === 3 ? 'third' : `#${k}`;
	const names = regions.slice(0, 3).map((r) => r.traits[0]);

	const steps: Step[] = [
		{
			title: `${fmt.int(n)} games, placed by what they share`,
			body: `Every dot is one of BoardGameGeek’s top ${fmt.int(n)}. Games with similar categories and mechanics sit close together, so the clumps are genres. Colour is average rating; bigger dots have more ratings.`,
			scene: { mode: 'rating', game: null, zoom: 1, spin: true }
		},
		{
			title: 'From far away, regions',
			body: `Zoomed out, the map names its regions by the traits that set them apart: ${names.join(', ')} and more. Click a region’s name to zoom into it.`,
			scene: { mode: 'rating', game: null, zoom: 0.95, spin: false }
		},
		{
			title: 'Up close, games',
			body: 'Zoom in and the regions give way to game names. Closer still, each game shows its rank, year and rating, and closest of all, what it is made of.',
			scene: { mode: 'rating', game: top.id, zoom: 6 }
		},
		{
			title: 'Newer games rate higher',
			body: `Colour by year: the recent games are everywhere, not just in one genre. Year published is the ${ordinal(yearsTop)} driver of the model’s predictions, ahead of any mechanic.`,
			scene: { mode: 'year', game: null, zoom: 1, spin: true },
			chapter: 'recipe'
		},
		{
			title: 'Co-operative games huddle together',
			body: `${count('mech:Cooperative Game')} of the top ${fmt.int(n)} are co-operative, and most of them sit in one neighbourhood: co-op is a genre, not just a rule.`,
			scene: {
				mode: 'trait',
				trait: 'mech:Cooperative Game',
				aimTrait: true,
				game: null,
				zoom: 2.2
			},
			chapter: 'traits'
		},
		{
			title: 'Wargames keep to themselves',
			body: `The ${count('cat:Wargame')} wargames share so many mechanics with each other, and so few with anything else, that they form their own island.`,
			scene: { mode: 'trait', trait: 'cat:Wargame', aimTrait: true, game: null, zoom: 2.2 },
			chapter: 'map'
		},
		{
			title: `BGG’s #1: ${top.name}`,
			body: `Rated ${fmt.r2(top.rating)}. Its traits alone predict ${fmt.r2(top.pred)}, so ${fmt.signed(top.magic)} is what we call magic sauce: everything its spec sheet can’t see. The lines lead to its most similar games.`,
			scene: { mode: 'rating', game: top.id },
			chapter: 'magic'
		},
		{
			title: `Most magic in the top 100: ${topMagic.name}`,
			body: `${topMagic.name} beats its prediction by ${fmt.signed(topMagic.magic)} points, more than any other top-100 game.`,
			scene: { mode: 'rating', game: topMagic.id },
			chapter: 'magic'
		},
		{
			title: 'Your turn',
			body: 'Fly with W A S D, use Q and E for down and up, drag to look around and scroll to zoom. Search for any game in the panel, or open a chapter for the full analysis.',
			scene: { mode: 'rating', game: null, zoom: 1, spin: true }
		}
	];

	let scroller = $state<HTMLElement>();
	let head = $state<HTMLElement>();
	let current = $state(0);

	$effect(() => {
		ui.scene = steps[current].scene;
	});

	onMount(() => {
		head?.focus({ preventScroll: true });
		const els = [...scroller!.querySelectorAll<HTMLElement>('.step')];
		const io = new IntersectionObserver(
			(entries) => {
				for (const e of entries)
					if (e.isIntersecting) current = Number((e.target as HTMLElement).dataset.i);
			},
			{ root: scroller, rootMargin: '-35% 0px -60% 0px' }
		);
		for (const el of els) io.observe(el);
		return () => io.disconnect();
	});

	function next(i: number) {
		const el = scroller?.querySelector<HTMLElement>(`[data-i="${i + 1}"]`);
		el?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' });
		el?.querySelector<HTMLElement>('h3')?.focus({ preventScroll: true });
	}
</script>

<div class="tour-head">
	<h2 tabindex="-1" bind:this={head}>Guided tour</h2>
	<span class="pos" aria-hidden="true">{current + 1} / {steps.length}</span>
	<button class="chip" onclick={onexit}>Exit tour</button>
</div>
<div class="tour" bind:this={scroller}>
	<p class="how">Scroll here, or over the map, to move through the story.</p>
	{#each steps as s, i (s.title)}
		<article
			class="step"
			class:on={i === current}
			data-i={i}
			aria-current={i === current ? 'step' : undefined}
		>
			<p class="n">{i + 1} of {steps.length}</p>
			<h3 tabindex="-1">{s.title}</h3>
			<p>{s.body}</p>
			<div class="acts">
				{#if s.chapter}
					<button class="chip" onclick={() => openChapter(s.chapter!)}
						>Read more: {chapterById.get(s.chapter)?.label}</button
					>
				{/if}
				{#if i < steps.length - 1}
					<button class="chip" onclick={() => next(i)}>Next</button>
				{:else}
					<button class="chip" onclick={onexit}>Explore freely</button>
					<button class="chip" onclick={() => openChapter('overview')}>Read the analysis</button>
				{/if}
			</div>
		</article>
	{/each}
	<div class="tail" aria-hidden="true"></div>
</div>

<style>
	.tour-head {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.75rem 0.9rem;
		border-bottom: 1px solid var(--border);
	}
	.tour-head h2 {
		font-size: 0.95rem;
		margin: 0;
		letter-spacing: normal;
	}
	.pos {
		color: var(--text-muted);
		font-size: 0.8rem;
		font-variant-numeric: tabular-nums;
		margin-right: auto;
	}
	.tour {
		flex: 1;
		overflow-y: auto;
		padding: 0 0.9rem;
		scroll-snap-type: y proximity;
	}
	.how {
		color: var(--text-muted);
		font-size: 0.8rem;
		margin: 0.75rem 0 0;
	}
	.step {
		min-height: 62%;
		padding: 1.25rem 0 1.5rem;
		padding-left: 0.75rem;
		scroll-snap-align: start;
		border-left: 3px solid transparent;
	}
	.step.on {
		border-left-color: var(--series-1);
	}
	.n {
		color: var(--text-muted);
		font-size: 0.75rem;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		margin: 0 0 0.3rem;
	}
	h3 {
		font-size: 1.1rem;
		line-height: 1.25;
		margin: 0 0 0.5rem;
		color: var(--text-primary);
	}
	.step p:not(.n) {
		color: var(--text-secondary);
		line-height: 1.5;
		margin: 0 0 0.75rem;
	}
	.acts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.tail {
		height: 40%;
	}
</style>
