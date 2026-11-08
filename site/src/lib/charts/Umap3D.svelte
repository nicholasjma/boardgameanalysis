<script lang="ts">
	import { onMount } from 'svelte';
	import { scaleSqrt } from 'd3';
	import { data, fmt, type Game } from '#lib/data.ts';
	import { eraIndex, eras, ratingBand, ratingBands } from '#lib/era.ts';
	import { openGame, ui } from '#lib/state.svelte.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';

	type Vec = [number, number, number];
	type P = { g: Game; p: Vec; near: number[] };
	type Mode = 'rating' | 'year' | 'trait';

	// --- Data -----------------------------------------------------------------------------------
	const pts: P[] = data.games
		.filter((g) => g.umap)
		.map((g) => ({ g, p: [...(g.umap as [number, number, number])], near: [] }));

	// Fit the bulk of the cloud (2nd–98th percentile on each axis) inside the unit sphere, so a
	// few outliers don't shrink everything else. Outliers simply sit a little outside the frame.
	const q = (k: number, f: number) => {
		const v = pts.map((d) => d.p[k]).sort((a, b) => a - b);
		return v[Math.round(f * (v.length - 1))];
	};
	const lo = [0, 1, 2].map((k) => q(k, 0.02));
	const hi = [0, 1, 2].map((k) => q(k, 0.98));
	const half = [0, 1, 2].map((k) => (hi[k] - lo[k]) / 2);
	const diag = Math.hypot(...half) || 1;
	for (const d of pts) d.p = d.p.map((v, k) => (v - (lo[k] + hi[k]) / 2) / diag) as Vec;
	const box = half.map((h) => h / diag);

	// Nearest neighbours in the embedding (brute force: 1,000² distances is cheap).
	const K = 5;
	for (const a of pts) {
		const best: [number, number][] = [];
		pts.forEach((b, j) => {
			if (a === b) return;
			const d = (a.p[0] - b.p[0]) ** 2 + (a.p[1] - b.p[1]) ** 2 + (a.p[2] - b.p[2]) ** 2;
			if (best.length < K || d < best[K - 1][0]) {
				best.push([d, j]);
				best.sort((x, y) => x[0] - y[0]);
				if (best.length > K) best.pop();
			}
		});
		a.near = best.map(([, j]) => j);
	}
	const indexById = new Map(pts.map((p, i) => [p.g.id, i]));
	const size = scaleSqrt()
		.domain([0, Math.max(...pts.map((p) => p.g.votes))])
		.range([2, 7.5]);
	const traitIndex = new Map(data.traitKeys.map((k, i) => [k, i]));
	const traits = [...data.traits].sort((a, b) => a.name.localeCompare(b.name));

	// --- View state -----------------------------------------------------------------------------
	let canvas: HTMLCanvasElement | undefined = $state();
	let width = $state(800);
	const height = $derived(Math.min(640, Math.max(380, width * 0.7)));
	let mode = $state<Mode>('rating');
	let playing = $state(true);
	let hover = $state<number | null>(null);
	let tip = $state<{ x: number; y: number } | null>(null);

	const DEFAULT = { yaw: 0.6, pitch: -0.35, zoom: 1 };
	let yaw = DEFAULT.yaw;
	let pitch = DEFAULT.pitch;
	let zoom = $state(DEFAULT.zoom);
	let intro = 0; // 0 → 1 as the points fly out from the centre
	let dirty = true;

	const traitBit = $derived(traitIndex.get(ui.trait) ?? -1);
	const traitName = $derived(data.traits.find((t) => t.key === ui.trait)?.name ?? '');
	const traitCount = $derived(pts.filter((p) => p.g.traits.includes(traitBit)).length);
	const focusId = $derived(hover !== null ? pts[hover].g.id : ui.hoverGame);
	const focus = $derived(focusId !== null ? (indexById.get(focusId) ?? null) : null);

	// Anything reactive that changes the picture asks for a redraw.
	$effect(() => {
		void [mode, traitBit, focus, zoom, width, height];
		dirty = true;
	});

	// --- Colours (read from CSS so light/dark both work) ----------------------------------------
	let palette: Record<string, string> = {};
	function readPalette() {
		if (!canvas) return;
		const cs = getComputedStyle(canvas);
		const v = (n: string) => cs.getPropertyValue(n).trim();
		palette = {
			surface: v('--surface-1'),
			grid: v('--grid') || v('--border'),
			text: v('--text-primary'),
			muted: v('--text-secondary'),
			neutral: v('--neutral-dot'),
			hi: v('--series-1'),
			font: getComputedStyle(document.body).fontFamily
		};
		for (let i = 1; i <= 5; i++) palette[`ord${i}`] = v(`--ord-${i}`);
		dirty = true;
	}

	function colorOf(g: Game): string {
		if (mode === 'rating') return palette[`ord${ratingBand(g.rating)}`];
		if (mode === 'year') return palette[`ord${eraIndex(g.year) + 1}`];
		return g.traits.includes(traitBit) ? palette.hi : palette.neutral;
	}

	// --- Projection -----------------------------------------------------------------------------
	const CAM = 3.4; // camera distance from the origin; the framed bulk lies within radius 1
	type S = { x: number; y: number; z: number; f: number };
	let screen: S[] = pts.map(() => ({ x: 0, y: 0, z: 0, f: 1 }));

	function project(
		p: [number, number, number],
		t: number,
		cy: number,
		cp: number,
		sy: number,
		sp: number
	): S {
		const [x0, y0, z0] = [p[0] * t, p[1] * t, p[2] * t];
		const x1 = x0 * cy + z0 * sy; // yaw about the vertical axis
		const z1 = -x0 * sy + z0 * cy;
		const y2 = y0 * cp - z1 * sp; // then pitch about the horizontal axis
		const z2 = y0 * sp + z1 * cp;
		const f = CAM / (CAM - z2);
		const R = Math.min(width * 0.4, height * 0.5) * zoom;
		return { x: width / 2 + x1 * f * R, y: height / 2 - y2 * f * R, z: z2, f };
	}

	// Dots shrink on small screens so the cloud doesn't turn into a blob, and grow a little with zoom.
	const dotScale = $derived(
		Math.max(0.55, Math.min(1, Math.min(width * 0.4, height * 0.5) / 250)) * Math.sqrt(zoom)
	);
	const ease = (t: number) => 1 - (1 - t) ** 3;
	const cube: [number, number, number][] = [-1, 1].flatMap((x) =>
		[-1, 1].flatMap((y) => [-1, 1].map((z) => [x, y, z] as [number, number, number]))
	);
	const edges = cube.flatMap((a, i) =>
		cube
			.map((b, j) => [i, j] as const)
			.filter(([, j]) => j > i && cube[j].filter((c, k) => c !== a[k]).length === 1)
	);

	function draw() {
		if (!canvas) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		const dpr = window.devicePixelRatio || 1;
		if (canvas.width !== Math.round(width * dpr)) canvas.width = Math.round(width * dpr);
		if (canvas.height !== Math.round(height * dpr)) canvas.height = Math.round(height * dpr);
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		ctx.clearRect(0, 0, width, height);

		const [cy, sy, cp, sp] = [Math.cos(yaw), Math.sin(yaw), Math.cos(pitch), Math.sin(pitch)];
		const t = ease(intro);

		// Reference cube: a faint frame that makes the rotation legible.
		const corners = cube.map((c) =>
			project([c[0] * box[0], c[1] * box[1], c[2] * box[2]], 1, cy, cp, sy, sp)
		);
		ctx.strokeStyle = palette.grid;
		ctx.lineWidth = 1;
		ctx.beginPath();
		for (const [i, j] of edges) {
			ctx.moveTo(corners[i].x, corners[i].y);
			ctx.lineTo(corners[j].x, corners[j].y);
		}
		ctx.stroke();

		// Each point flies out on its own schedule: higher-ranked games arrive first.
		screen = pts.map((d, i) =>
			project(d.p, ease(Math.min(1, Math.max(0, t * 1.5 - (i / pts.length) * 0.5))), cy, cp, sy, sp)
		);
		const order = screen.map((_, i) => i).sort((a, b) => screen[a].z - screen[b].z);

		const traitMode = mode === 'trait';
		for (const i of order) {
			const s = screen[i];
			const g = pts[i].g;
			const on = !traitMode || g.traits.includes(traitBit);
			// Depth cue: far points are smaller and fainter.
			const depth = Math.max(0, Math.min(1, (s.z + 1) / 2)); // 0 (far) … 1 (near)
			ctx.globalAlpha =
				(on ? 0.55 + 0.45 * depth : 0.25 + 0.2 * depth) * (focus !== null ? 0.7 : 1);
			ctx.beginPath();
			ctx.arc(s.x, s.y, size(g.votes) * s.f * dotScale, 0, Math.PI * 2);
			ctx.fillStyle = colorOf(g);
			ctx.fill();
			ctx.lineWidth = 1;
			ctx.strokeStyle = palette.surface;
			ctx.stroke();
		}
		ctx.globalAlpha = 1;

		// Focused game: links to its nearest neighbours, then a ring.
		const labels: { i: number; strong: boolean }[] = [];
		if (focus !== null) {
			const s = screen[focus];
			ctx.strokeStyle = palette.text;
			ctx.globalAlpha = 0.55;
			ctx.lineWidth = 1;
			ctx.beginPath();
			for (const j of pts[focus].near) {
				ctx.moveTo(s.x, s.y);
				ctx.lineTo(screen[j].x, screen[j].y);
				labels.push({ i: j, strong: false });
			}
			ctx.stroke();
			ctx.globalAlpha = 1;
			for (const j of pts[focus].near) ring(ctx, j, 1.5);
			ring(ctx, focus, 2.5);
			labels.unshift({ i: focus, strong: true });
		} else if (intro >= 1) {
			// A few direct labels: the best-ranked games (in trait mode, the best-ranked matches).
			const pool = traitMode
				? pts.map((_, i) => i).filter((i) => pts[i].g.traits.includes(traitBit))
				: pts.map((_, i) => i);
			for (const i of pool.slice(0, width < 520 ? 4 : 8)) labels.push({ i, strong: false });
		}
		// While the tooltip is up it names the game and its neighbours, so skip canvas labels.
		drawLabels(ctx, hover !== null ? [] : labels);
	}

	function ring(ctx: CanvasRenderingContext2D, i: number, w: number) {
		const s = screen[i];
		ctx.beginPath();
		ctx.arc(s.x, s.y, size(pts[i].g.votes) * s.f * dotScale + 3, 0, Math.PI * 2);
		ctx.strokeStyle = palette.text;
		ctx.lineWidth = w;
		ctx.stroke();
	}

	function drawLabels(ctx: CanvasRenderingContext2D, labels: { i: number; strong: boolean }[]) {
		const placed: [number, number, number, number][] = [];
		ctx.textBaseline = 'middle';
		ctx.lineJoin = 'round';
		for (const { i, strong } of labels) {
			const s = screen[i];
			ctx.font = `${strong ? 600 : 500} ${strong ? 13 : 12}px ${palette.font}`;
			const text = pts[i].g.name.length > 32 ? pts[i].g.name.slice(0, 31) + '…' : pts[i].g.name;
			const w = ctx.measureText(text).width;
			const left = s.x > width - w - 24;
			const x = left ? s.x - 9 - w : s.x + 9;
			const box: [number, number, number, number] = [x - 2, s.y - 9, x + w + 2, s.y + 9];
			if (
				!strong &&
				placed.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])
			)
				continue;
			placed.push(box);
			ctx.lineWidth = 4;
			ctx.strokeStyle = palette.surface;
			ctx.strokeText(text, x, s.y);
			ctx.fillStyle = strong ? palette.text : palette.muted;
			ctx.fillText(text, x, s.y);
		}
	}

	// --- Interaction ----------------------------------------------------------------------------
	let drag = $state<{ x: number; y: number; moved: number } | null>(null);

	function pick(e: PointerEvent): number | null {
		const rect = canvas!.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;
		let best: number | null = null;
		let bestD = 16 ** 2;
		screen.forEach((s, i) => {
			const d = (s.x - mx) ** 2 + (s.y - my) ** 2 - s.z * 20; // prefer nearer points on ties
			if (d < bestD) [best, bestD] = [i, d];
		});
		return best;
	}

	function onDown(e: PointerEvent) {
		drag = { x: e.clientX, y: e.clientY, moved: 0 };
		canvas!.setPointerCapture(e.pointerId);
	}
	function onMove(e: PointerEvent) {
		if (drag) {
			const dx = e.clientX - drag.x;
			const dy = e.clientY - drag.y;
			drag = { x: e.clientX, y: e.clientY, moved: drag.moved + Math.abs(dx) + Math.abs(dy) };
			if (drag.moved > 4) {
				playing = false;
				hover = null;
				tip = null;
				yaw += dx * 0.008;
				if (e.pointerType === 'mouse') pitch = Math.max(-1.4, Math.min(1.4, pitch + dy * 0.008));
				dirty = true;
				return;
			}
		}
		hover = pick(e);
		tip = hover !== null ? { x: screen[hover].x, y: screen[hover].y } : null;
	}
	function onUp(e: PointerEvent) {
		if (drag && drag.moved <= 4) {
			const i = pick(e);
			if (i !== null) openGame(pts[i].g.id);
		}
		drag = null;
	}
	function onLeave() {
		if (!drag) {
			hover = null;
			tip = null;
		}
	}
	function onKey(e: KeyboardEvent) {
		const step = 0.12;
		const keys: Record<string, () => void> = {
			ArrowLeft: () => (yaw -= step),
			ArrowRight: () => (yaw += step),
			ArrowUp: () => (pitch = Math.max(-1.4, pitch - step)),
			ArrowDown: () => (pitch = Math.min(1.4, pitch + step)),
			'+': () => zoomBy(1.2),
			'=': () => zoomBy(1.2),
			'-': () => zoomBy(1 / 1.2),
			' ': () => (playing = !playing)
		};
		if (keys[e.key]) {
			e.preventDefault();
			if (e.key.startsWith('Arrow')) playing = false;
			keys[e.key]();
			dirty = true;
		}
	}
	const zoomBy = (k: number) => (zoom = Math.max(0.6, Math.min(3, zoom * k)));
	function reset() {
		yaw = DEFAULT.yaw;
		pitch = DEFAULT.pitch;
		zoom = DEFAULT.zoom;
		dirty = true;
	}

	// --- Lifecycle: animate only while on screen ------------------------------------------------
	onMount(() => {
		const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (reduced) {
			playing = false;
			intro = 1;
		}
		readPalette();
		const mo = new MutationObserver(readPalette);
		mo.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['data-theme', 'class']
		});
		const mq = matchMedia('(prefers-color-scheme: dark)');
		mq.addEventListener('change', readPalette);

		let visible = false;
		let started = false;
		const io = new IntersectionObserver(
			([e]) => {
				visible = e.isIntersecting;
				if (visible) started = true;
			},
			{ threshold: 0.15 }
		);
		io.observe(canvas!);

		let raf = 0;
		let last = performance.now();
		const tick = (now: number) => {
			const raw = (now - last) / 1000;
			const dt = Math.min(0.064, raw); // cap rotation steps after a stall
			last = now;
			if (visible) {
				if (started && intro < 1) {
					intro = Math.min(1, intro + Math.min(0.25, raw) / 1.6);
					dirty = true;
				}
				if (playing && !drag) {
					yaw += dt * 0.12;
					dirty = true;
				}
				if (dirty) {
					dirty = false;
					draw();
					if (hover !== null) tip = { x: screen[hover].x, y: screen[hover].y };
				}
			}
			raf = requestAnimationFrame(tick);
		};
		raf = requestAnimationFrame(tick);
		return () => {
			cancelAnimationFrame(raf);
			io.disconnect();
			mo.disconnect();
			mq.removeEventListener('change', readPalette);
		};
	});

	const tableRows = pts.slice(0, 1000);
</script>

<div class="controls">
	<div class="seg" role="group" aria-label="Colour points by">
		<span class="lbl">Colour by</span>
		<button class="chip" aria-pressed={mode === 'rating'} onclick={() => (mode = 'rating')}
			>Rating</button
		>
		<button class="chip" aria-pressed={mode === 'year'} onclick={() => (mode = 'year')}>Year</button
		>
		<button class="chip" aria-pressed={mode === 'trait'} onclick={() => (mode = 'trait')}
			>A trait</button
		>
	</div>
	{#if mode === 'trait'}
		<label>
			<span class="visually-hidden">Highlight a category or mechanic</span>
			<select bind:value={ui.trait}>
				<optgroup label="Mechanics">
					{#each traits.filter((t) => t.kind === 'mechanic') as t (t.key)}
						<option value={t.key}>{t.name}</option>
					{/each}
				</optgroup>
				<optgroup label="Categories">
					{#each traits.filter((t) => t.kind === 'category') as t (t.key)}
						<option value={t.key}>{t.name}</option>
					{/each}
				</optgroup>
			</select>
		</label>
	{/if}
	<div class="view" role="group" aria-label="View controls">
		<button class="chip" aria-pressed={playing} onclick={() => (playing = !playing)}>
			{playing ? 'Pause' : 'Rotate'}
		</button>
		<button class="chip icon" aria-label="Zoom in" onclick={() => zoomBy(1.25)}>+</button>
		<button class="chip icon" aria-label="Zoom out" onclick={() => zoomBy(1 / 1.25)}>−</button>
		<button class="chip" onclick={reset}>Reset</button>
	</div>
</div>

<ul class="legend">
	{#if mode === 'rating'}
		<li class="ttl">Average rating</li>
		{#each ratingBands as b, i (b.label)}
			<li><span class="swatch dot" style:background="var(--ord-{i + 1})"></span>{b.label}</li>
		{/each}
	{:else if mode === 'year'}
		<li class="ttl">Year published</li>
		{#each eras as e, i (e.label)}
			<li><span class="swatch dot" style:background="var(--ord-{i + 1})"></span>{e.label}</li>
		{/each}
	{:else}
		<li>
			<span class="swatch dot" style:background="var(--series-1)"></span>{traitName} ({traitCount})
		</li>
		<li><span class="swatch dot" style:background="var(--neutral-dot)"></span>Other games</li>
	{/if}
	<li class="ttl">· dot size = number of ratings</li>
</ul>

<figure class="wrap" bind:clientWidth={width}>
	<canvas
		bind:this={canvas}
		style:width="{width}px"
		style:height="{height}px"
		class:grabbing={drag !== null}
		tabindex="0"
		aria-roledescription="3D scatter plot"
		aria-label="Rotating 3D map of the top {pts.length} games, placed by shared categories and mechanics. Arrow keys rotate, plus and minus zoom, space pauses."
		onpointerdown={onDown}
		onpointermove={onMove}
		onpointerup={onUp}
		onpointerleave={onLeave}
		onkeydown={onKey}
	></canvas>
	{#if hover !== null && tip}
		{@const d = pts[hover]}
		<Tooltip x={tip.x} y={tip.y} {width}>
			<span class="t">{d.g.name} <span class="muted">({d.g.year})</span></span>
			<div class="row"><span>Rank</span><span class="v">#{d.g.rank}</span></div>
			<div class="row"><span>Rating</span><span class="v">{fmt.r2(d.g.rating)}</span></div>
			<div class="near">
				Closest: {d.near
					.slice(0, 3)
					.map((j) => pts[j].g.name)
					.join(', ')}
			</div>
		</Tooltip>
	{/if}
	<p class="foot">
		Drag to rotate · hover a game to see its nearest neighbours · click to open it. The axes have no
		units: only closeness means something.
	</p>
</figure>

<details class="table-view">
	<summary>Table view: each game's nearest neighbours</summary>
	<div class="scroll">
		<table>
			<thead><tr><th>Rank</th><th>Game</th><th>Closest on the map</th></tr></thead>
			<tbody>
				{#each tableRows as d (d.g.id)}
					<tr>
						<td>{d.g.rank}</td>
						<td>{d.g.name}</td>
						<td
							>{d.near
								.slice(0, 3)
								.map((j) => pts[j].g.name)
								.join(', ')}</td
						>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</details>

<style>
	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
		margin-bottom: 0.75rem;
	}
	.seg,
	.view {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
	}
	.view {
		margin-left: auto;
	}
	.lbl,
	.ttl {
		color: var(--text-muted);
		font-size: 0.82rem;
	}
	.icon {
		width: 2rem;
		padding: 0.25rem 0;
		text-align: center;
	}
	select {
		max-width: 100%;
		border: 1px solid var(--border);
		background: var(--surface-1);
		border-radius: 8px;
		padding: 0.3rem 0.5rem;
		font-size: 0.85rem;
	}
	.wrap {
		position: relative;
		margin: 0;
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 12px;
	}
	canvas {
		display: block;
		cursor: grab;
		touch-action: pan-y;
	}
	canvas.grabbing {
		cursor: grabbing;
	}
	canvas:focus-visible {
		outline-offset: -2px;
	}
	.near {
		margin-top: 0.25rem;
		color: var(--text-muted);
	}
	.foot {
		font-size: 0.8rem;
		color: var(--text-muted);
		margin: 0;
		padding: 0.5rem 0.75rem 0.6rem;
		border-top: 1px solid var(--border);
	}
</style>
