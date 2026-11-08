<script lang="ts">
	import { onMount, tick, untrack } from 'svelte';
	import { prefersReducedMotion } from 'svelte/motion';
	import { data, fmt, type Game } from '#lib/data.ts';
	import { interpolateLab } from 'd3';
	import { chapterById, chapterHref, chapters } from '#lib/chapters.ts';
	import {
		backToChapter,
		openChapter,
		openGame,
		ui,
		type MapMode,
		type Scene
	} from '#lib/state.svelte.ts';
	import {
		box,
		dotSize,
		indexById,
		N_SIMILAR,
		pts,
		regions,
		similarTo,
		traitCentre,
		traitIndex,
		type Vec
	} from '#lib/space.ts';
	import Tooltip from '#lib/components/Tooltip.svelte';
	import Tour from '#lib/components/Tour.svelte';

	const traits = [...data.traits].sort((a, b) => a.name.localeCompare(b.name));
	const snapshot = new Date(`${data.meta.snapshot}-01`).toLocaleDateString('en-US', {
		month: 'long',
		year: 'numeric',
		timeZone: 'UTC'
	});

	// --- View state -----------------------------------------------------------------------------
	let canvas: HTMLCanvasElement | undefined = $state();
	let panel: HTMLElement | undefined = $state();
	let selHead: HTMLElement | undefined = $state();
	let width = $state(1200);
	let height = $state(800);
	let mode = $state<MapMode>('rating');
	let playing = $state(true);
	let hover = $state<number | null>(null);
	let tip = $state<{ x: number; y: number } | null>(null);

	const DEFAULT = { yaw: 0.6, pitch: -0.35, zoom: 1 };
	const ZOOM = [0.6, 60] as const;
	let yaw = DEFAULT.yaw;
	let pitch = DEFAULT.pitch;
	let zoom = $state(DEFAULT.zoom);
	// The camera orbits `center`, which eases toward `aim`; WASD moves both.
	let aim: Vec = [0, 0, 0];
	let center: Vec = [0, 0, 0];
	let zoomNow = DEFAULT.zoom;
	// How far the camera sits from `center`, as a multiple of the default for this zoom. Turning
	// re-pivots onto whatever is in the middle of the view, which changes this, not the picture.
	let reach = 1;
	let reachAim = 1;
	let selected = $state<number | null>(null);
	let listHover = $state<number | null>(null);
	const similar = $derived(selected !== null ? similarTo(selected) : []);
	const selectedGame = $derived(selected !== null ? pts[selected].g : null);
	let intro = 0; // 0 → 1 as the points fly out from the centre
	let dirty = true;

	// The map sits behind a chapter while one is open: skip drawing and ignore flying keys.
	const covered = $derived(ui.pane !== null && !ui.paneHidden);
	const returnTo = $derived(ui.pane && ui.paneHidden ? chapterById.get(ui.pane) : undefined);

	const traitBit = $derived(traitIndex.get(ui.trait) ?? -1);
	const traitName = $derived(data.traits.find((t) => t.key === ui.trait)?.name ?? '');
	const traitCount = $derived(pts.filter((p) => p.g.traits.includes(traitBit)).length);
	const hoverIdx = $derived(
		hover ?? (ui.hoverGame !== null ? (indexById.get(ui.hoverGame) ?? null) : null)
	);
	// What the map highlights: the selection stays put while you point at its neighbours;
	// with nothing selected, hovering a game shows its nearest neighbours.
	const focus = $derived(selected ?? hoverIdx);
	const links = $derived(
		focus === null ? [] : focus === selected ? similar.map((s) => s.i) : pts[focus].near
	);

	// Anything reactive that changes the picture asks for a redraw.
	$effect(() => {
		void [mode, traitBit, focus, links, listHover, hover, zoom, width, height, covered];
		dirty = true;
	});

	// Where the cloud is drawn: beside the side panel on wide screens, above the sheet on narrow.
	const HDR = 56;
	const wide = $derived(width >= 860);
	const frame = $derived(
		wide
			? {
					cx: 344 + (width - 344) / 2,
					cy: HDR + (height - HDR) / 2 + 10,
					r: Math.min((width - 344) * 0.42, (height - HDR) * 0.42)
				}
			: {
					cx: width / 2,
					cy: HDR + 44 + (height * 0.56 - HDR - 44) / 2,
					r: Math.min(width * 0.44, (height * 0.56 - HDR - 44) * 0.5)
				}
	);

	// --- Colours (read from CSS so light/dark both work) ----------------------------------------
	let palette: Record<string, string> = {};
	function readPalette() {
		if (!canvas) return;
		const cs = getComputedStyle(canvas);
		const v = (n: string) => cs.getPropertyValue(n).trim();
		palette = {
			surface: v('--surface-1'),
			page: v('--page'),
			border: v('--border'),
			grid: v('--grid') || v('--border'),
			text: v('--text-primary'),
			muted: v('--text-secondary'),
			faint: v('--text-muted'),
			neutral: v('--neutral-dot'),
			hi: v('--series-1'),
			font: getComputedStyle(document.body).fontFamily
		};
		for (let i = 1; i <= 5; i++) palette[`ord${i}`] = v(`--ord-${i}`);
		palette.warm = v('--series-2');
		palette.hot = v('--div-neg');
		buildColours();
		dirty = true;
	}

	// Rating: cool below 8, warm from 8 up, with a sharp step at 8 so the 8+ games jump out.
	// Year: a quiet ramp from old to new, then orange for the newest releases.
	const RATING = { lo: 6.9, cut: 8, hi: 8.7 };
	const YEAR = { lo: 1995, hi: 2023, recent: 2024, newest: 2025 };
	const newest = (g: Game) => g.year >= YEAR.newest;
	const newestCount = pts.filter((d) => newest(d.g)).length;
	/** Drawn last and a little larger, so they sit on top of the cloud. */
	const standout = (g: Game) =>
		mode === 'rating' ? g.rating >= RATING.cut : mode === 'year' ? g.year >= YEAR.recent : false;

	function ramp(stops: [number, string][], x: number): string {
		if (x <= stops[0][0]) return stops[0][1];
		for (let k = 1; k < stops.length; k++) {
			const [x1, c1] = stops[k];
			const [x0, c0] = stops[k - 1];
			if (x <= x1) return interpolateLab(c0, c1)((x - x0) / (x1 - x0));
		}
		return stops[stops.length - 1][1];
	}
	let colours: Record<'rating' | 'year', string[]> = { rating: [], year: [] };
	function buildColours() {
		const P = palette;
		colours = {
			rating: pts.map(({ g }) =>
				ramp(
					[
						[RATING.lo, P.ord1],
						[RATING.cut - 0.01, P.ord4],
						[RATING.cut, P.warm],
						[RATING.hi, P.hot]
					],
					g.rating
				)
			),
			year: pts.map(({ g }) =>
				g.year >= YEAR.newest
					? P.warm
					: g.year >= YEAR.recent
						? interpolateLab(P.surface, P.warm)(0.55)
						: ramp(
								[
									[YEAR.lo, P.ord1],
									[YEAR.hi, P.ord5]
								],
								g.year
							)
			)
		};
	}

	function colorOf(i: number): string {
		if (mode === 'trait') return pts[i].g.traits.includes(traitBit) ? palette.hi : palette.neutral;
		return colours[mode][i];
	}

	// --- Camera ---------------------------------------------------------------------------------
	const CAM = 3.4; // camera distance from `center` at zoom 1; the framed bulk lies within radius 1
	const NEAR = 0.15; // anything closer to the camera than this is behind it, or too close to draw
	type S = { x: number; y: number; z: number; f: number; vis: boolean };
	let screen: S[] = pts.map(() => ({ x: 0, y: 0, z: 0, f: 1, vis: false }));
	let rot = { cy: 1, sy: 0, cp: 1, sp: 0 };

	function project(p: Vec, t = 1): S {
		const { cy, sy, cp, sp } = rot;
		const [x0, y0, z0] = [p[0] * t - center[0], p[1] * t - center[1], p[2] * t - center[2]];
		const x1 = x0 * cy + z0 * sy; // yaw about the vertical axis
		const z1 = -x0 * sy + z0 * cy;
		const y2 = y0 * cp - z1 * sp; // then pitch about the horizontal axis
		const z2 = y0 * sp + z1 * cp;
		// Zoomed in, the camera also moves closer, so nearby games spread out in depth.
		const cam = CAM / Math.sqrt(zoomNow);
		const depth = cam * reach - z2;
		if (depth < NEAR) return { x: NaN, y: NaN, z: z2, f: Infinity, vis: false };
		const f = cam / depth;
		const R = frame.r * zoomNow;
		const x = frame.cx + x1 * f * R;
		const y = frame.cy - y2 * f * R;
		const vis = x > -60 && x < width + 60 && y > -60 && y < height + 60;
		return { x, y, z: z2, f, vis };
	}

	/** A camera-space direction (right, up, toward the viewer) in world coordinates. */
	function toWorld(x1: number, y2: number, z2: number): Vec {
		const { cy, sy, cp, sp } = rot;
		const y0 = y2 * cp + z2 * sp;
		const z1 = -y2 * sp + z2 * cp;
		return [x1 * cy - z1 * sy, y0, x1 * sy + z1 * cy];
	}

	// Dots shrink on small screens so the cloud doesn't turn into a blob, and grow a little with zoom.
	const baseDot = $derived(Math.max(0.55, Math.min(1, frame.r / 250)));
	let dotScale = 1;
	const ease = (t: number) => 1 - (1 - t) ** 3;
	const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
	const cube: Vec[] = [-1, 1].flatMap((x) =>
		[-1, 1].flatMap((y) => [-1, 1].map((z) => [x, y, z] as Vec))
	);
	const edges = cube.flatMap((a, i) =>
		cube
			.map((b, j) => [i, j] as const)
			.filter(([, j]) => j > i && cube[j].filter((c, k) => c !== a[k]).length === 1)
	);

	// --- Semantic zoom ------------------------------------------------------------------------
	// What gets written on the map depends on how close you are: from far away, regions named by
	// their traits; closer, game names; up close, cards with rank, year and rating; closer still,
	// the traits each game is built from. `mag` is how much bigger a game looks than at the start.
	const LEVEL = { name: 1.55, card: 3, detail: 5.2 };
	const mag = (i: number) => zoomNow * screen[i].f;
	const regionAlpha = () => (focus !== null ? 0 : clamp01((2.1 - zoomNow) / 0.8));
	let regionHits: { id: number; b: [number, number, number, number] }[] = [];
	// Game labels and cards are part of their game: pointing at one points at the game.
	let labelHits: { i: number; b: [number, number, number, number] }[] = [];

	function draw() {
		if (!canvas) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;
		const dpr = window.devicePixelRatio || 1;
		if (canvas.width !== Math.round(width * dpr)) canvas.width = Math.round(width * dpr);
		if (canvas.height !== Math.round(height * dpr)) canvas.height = Math.round(height * dpr);
		ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
		ctx.clearRect(0, 0, width, height);

		rot = { cy: Math.cos(yaw), sy: Math.sin(yaw), cp: Math.cos(pitch), sp: Math.sin(pitch) };
		const t = ease(intro);
		dotScale = baseDot * Math.min(1.6, Math.sqrt(zoomNow));

		// Reference cube: a faint frame that makes the rotation legible.
		const corners = cube.map((c) => project([c[0] * box[0], c[1] * box[1], c[2] * box[2]]));
		ctx.strokeStyle = palette.grid;
		ctx.lineWidth = 1;
		ctx.beginPath();
		for (const [i, j] of edges) {
			if (!Number.isFinite(corners[i].f) || !Number.isFinite(corners[j].f)) continue;
			ctx.moveTo(corners[i].x, corners[i].y);
			ctx.lineTo(corners[j].x, corners[j].y);
		}
		ctx.stroke();

		// Each point flies out on its own schedule: higher-ranked games arrive first.
		screen = pts.map((d, i) => project(d.p, ease(clamp01(t * 1.5 - (i / pts.length) * 0.5))));
		const order = screen.map((_, i) => i).sort((a, b) => screen[a].z - screen[b].z);

		const traitMode = mode === 'trait';
		// Standouts (8+ ratings, the newest games) go in a second pass, on top of the rest.
		const top = order.filter((i) => standout(pts[i].g));
		for (const i of [...order.filter((i) => !standout(pts[i].g)), ...top]) {
			const s = screen[i];
			if (!s.vis) continue;
			const g = pts[i].g;
			const on = !traitMode || g.traits.includes(traitBit);
			const big = mode === 'year' && newest(g) ? 1.5 : 1;
			// Depth cue: far points are smaller and fainter.
			const depth = clamp01((s.z + 1) / 2); // 0 (far) … 1 (near)
			ctx.globalAlpha =
				(on ? 0.55 + 0.45 * depth : 0.22 + 0.18 * depth) * (focus !== null ? 0.7 : 1);
			if (big > 1) ctx.globalAlpha = 1;
			ctx.beginPath();
			ctx.arc(s.x, s.y, Math.min(30, dotSize(g.votes) * s.f * dotScale * big), 0, Math.PI * 2);
			ctx.fillStyle = colorOf(i);
			ctx.fill();
			ctx.lineWidth = big > 1 ? 2 : 1;
			ctx.strokeStyle = big > 1 ? palette.text : palette.surface;
			ctx.stroke();
		}
		ctx.globalAlpha = 1;

		// Labels keep clear of the floating panels as well as of each other.
		const placed: [number, number, number, number][] = obstacles();
		regionHits = [];
		labelHits = [];
		if (intro < 1) return;

		// Focused game: links to its most similar games (or nearest neighbours), then rings.
		if (focus !== null && screen[focus].vis) {
			const s = screen[focus];
			ctx.strokeStyle = palette.text;
			ctx.globalAlpha = 0.55;
			ctx.lineWidth = 1;
			ctx.beginPath();
			for (const j of links) {
				if (!screen[j].vis) continue;
				ctx.moveTo(s.x, s.y);
				ctx.lineTo(screen[j].x, screen[j].y);
			}
			ctx.stroke();
			ctx.globalAlpha = 1;
			for (const j of links) if (screen[j].vis) ring(ctx, j, 1.5);
			ring(ctx, focus, 2.5);
			if (listHover !== null && screen[listHover].vis) ring(ctx, listHover, 3);
		}
		if (hover !== null && hover !== focus && screen[hover].vis) ring(ctx, hover, 3);

		if (focus !== null) {
			label(ctx, placed, focus, mag(focus) >= LEVEL.card ? 'card' : 'strong');
			if (listHover !== null) label(ctx, placed, listHover, 'strong');
			for (const j of links) label(ctx, placed, j, mag(j) >= LEVEL.card ? 'card' : 'name');
		}

		// Up close: cards for the nearest games, then names for the most prominent ones in view.
		const near = screen
			.map((s, i) => i)
			.filter((i) => screen[i].vis && mag(i) >= LEVEL.name && (!traitMode || on(i)))
			.sort((a, b) => mag(b) * dotSize(pts[b].g.votes) - mag(a) * dotSize(pts[a].g.votes));
		const cards = near.filter((i) => mag(i) >= LEVEL.card).slice(0, wide ? 6 : 3);
		for (const i of cards) label(ctx, placed, i, 'card');
		for (const i of near.slice(0, wide ? 22 : 9)) label(ctx, placed, i, 'name');

		if (mode === 'year' && focus === null)
			for (const i of pts.map((_, i) => i).filter((i) => newest(pts[i].g)))
				label(ctx, placed, i, 'strong');

		// Far away: name the regions instead.
		const a = regionAlpha();
		if (a > 0.02) {
			ctx.globalAlpha = a;
			for (const r of regions) {
				const s = project(r.c);
				if (!s.vis) continue;
				const b = regionLabel(ctx, placed, r.name.toUpperCase(), `${r.n} games`, s.x, s.y);
				if (b) regionHits.push({ id: r.id, b });
			}
			ctx.globalAlpha = 1;
		}
		function on(i: number) {
			return pts[i].g.traits.includes(traitBit);
		}
	}

	function obstacles(): [number, number, number, number][] {
		const host = canvas!.getBoundingClientRect();
		return [...canvas!.parentElement!.querySelectorAll<HTMLElement>('.hud, .panel')].map((el) => {
			const r = el.getBoundingClientRect();
			return [
				r.left - host.left - 4,
				r.top - host.top - 4,
				r.right - host.left + 4,
				r.bottom - host.top + 4
			];
		});
	}

	function ring(ctx: CanvasRenderingContext2D, i: number, w: number) {
		const s = screen[i];
		ctx.beginPath();
		ctx.arc(s.x, s.y, Math.min(30, dotSize(pts[i].g.votes) * s.f * dotScale) + 3, 0, Math.PI * 2);
		ctx.strokeStyle = palette.text;
		ctx.lineWidth = w;
		ctx.stroke();
	}

	const overlaps = (b: number[], placed: number[][]) =>
		placed.some((p) => b[0] < p[2] && b[2] > p[0] && b[1] < p[3] && b[3] > p[1]);
	const short = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

	function label(
		ctx: CanvasRenderingContext2D,
		placed: [number, number, number, number][],
		i: number,
		kind: 'strong' | 'name' | 'card'
	) {
		const s = screen[i];
		if (!s.vis) return;
		const g = pts[i].g;
		const r = Math.min(30, dotSize(g.votes) * s.f * dotScale);
		ctx.textBaseline = 'middle';
		ctx.lineJoin = 'round';
		if (kind === 'card') {
			const detail = mag(i) >= LEVEL.detail;
			const lines = [
				short(g.name, 34),
				`#${g.rank} · ${g.year} · ${fmt.r2(g.rating)}`,
				...(detail
					? [
							g.traits
								.slice(0, 3)
								.map((k) => data.traits[k]?.name)
								.join(', ')
						]
					: [])
			].map((l, k) => (k === 2 ? short(l, 40) : l));
			const fonts = [
				`600 13px ${palette.font}`,
				`500 11.5px ${palette.font}`,
				`500 11px ${palette.font}`
			];
			const w =
				Math.max(
					...lines.map((l, k) => {
						ctx.font = fonts[k];
						return ctx.measureText(l).width;
					})
				) + 16;
			const h = 10 + lines.length * 16;
			const right = s.x + r + 8 + w < width - 4;
			const x = right ? s.x + r + 8 : Math.max(4, s.x - r - 8 - w);
			const y = Math.max(HDR + 4, Math.min(height - h - 4, s.y - h / 2));
			const b: [number, number, number, number] = [x, y, x + w, y + h];
			if (overlaps(b, placed)) return;
			placed.push(b);
			labelHits.push({ i, b });
			ctx.beginPath();
			ctx.roundRect(x, y, w, h, 7);
			ctx.fillStyle = palette.surface;
			ctx.globalAlpha = 0.94;
			ctx.fill();
			ctx.globalAlpha = 1;
			ctx.strokeStyle = palette.border;
			ctx.lineWidth = 1;
			ctx.stroke();
			lines.forEach((l, k) => {
				ctx.font = fonts[k];
				ctx.fillStyle = k === 0 ? palette.text : palette.muted;
				ctx.fillText(l, x + 8, y + 13 + k * 16);
			});
			return;
		}
		const strong = kind === 'strong';
		ctx.font = `${strong ? 600 : 500} ${strong ? 13 : 12}px ${palette.font}`;
		const text = short(g.name, 32);
		const w = ctx.measureText(text).width;
		const left = s.x > width - w - 24;
		const x = Math.max(4, Math.min(width - w - 4, left ? s.x - r - 6 - w : s.x + r + 6));
		const b: [number, number, number, number] = [x - 2, s.y - 9, x + w + 2, s.y + 9];
		if (!strong && overlaps(b, placed)) return;
		placed.push(b);
		labelHits.push({ i, b });
		ctx.lineWidth = 4;
		ctx.strokeStyle = palette.surface;
		ctx.strokeText(text, x, s.y);
		ctx.fillStyle = strong ? palette.text : palette.muted;
		ctx.fillText(text, x, s.y);
	}

	function regionLabel(
		ctx: CanvasRenderingContext2D,
		placed: [number, number, number, number][],
		title: string,
		sub: string,
		cx: number,
		cy: number
	): [number, number, number, number] | null {
		ctx.textBaseline = 'middle';
		ctx.textAlign = 'center';
		ctx.font = `700 11.5px ${palette.font}`;
		const w1 = ctx.measureText(title).width;
		ctx.font = `500 11px ${palette.font}`;
		const w = Math.max(w1, ctx.measureText(sub).width) + 8;
		const b: [number, number, number, number] = [cx - w / 2, cy - 15, cx + w / 2, cy + 15];
		if (overlaps(b, placed)) {
			ctx.textAlign = 'start';
			return null;
		}
		placed.push(b);
		ctx.lineWidth = 4;
		ctx.strokeStyle = palette.surface;
		ctx.font = `700 11.5px ${palette.font}`;
		ctx.strokeText(title, cx, cy - 7);
		ctx.fillStyle = palette.text;
		ctx.fillText(title, cx, cy - 7);
		ctx.font = `500 11px ${palette.font}`;
		ctx.strokeText(sub, cx, cy + 8);
		ctx.fillStyle = palette.muted;
		ctx.fillText(sub, cx, cy + 8);
		ctx.textAlign = 'start';
		return b;
	}

	// --- Pointer: drag to look, wheel or pinch to zoom, click to select --------------------------
	let drag = $state<{ x: number; y: number; moved: number } | null>(null);
	// Plain collections on purpose: read by the animation loop, never rendered.
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const touches = new Map<number, { x: number; y: number }>();
	let pinch = 0;

	function local(e: { clientX: number; clientY: number }) {
		const rect = canvas!.getBoundingClientRect();
		return { mx: e.clientX - rect.left, my: e.clientY - rect.top };
	}
	function pick(e: PointerEvent): number | null {
		const { mx, my } = local(e);
		let best: number | null = null;
		let bestD = 16 ** 2;
		screen.forEach((s, i) => {
			if (!s.vis) return;
			const d = (s.x - mx) ** 2 + (s.y - my) ** 2 - s.z * 20; // prefer nearer points on ties
			if (d < bestD) [best, bestD] = [i, d];
		});
		return best;
	}
	function pickLabel(e: PointerEvent): number | null {
		const { mx, my } = local(e);
		const inside = ({ b }: { b: number[] }) => mx >= b[0] && mx <= b[2] && my >= b[1] && my <= b[3];
		return labelHits.findLast(inside)?.i ?? null;
	}
	function pickRegion(e: PointerEvent): number | null {
		const { mx, my } = local(e);
		return (
			regionHits.find(({ b }) => mx >= b[0] && mx <= b[2] && my >= b[1] && my <= b[3])?.id ?? null
		);
	}

	/**
	 * Turn around what you are looking at. Moves the orbit point onto the game nearest the middle
	 * of the view (the selected game if it is there), at that game's depth, without moving the
	 * camera: the picture stays put and the next drag or arrow key pivots on that game rather
	 * than on a point far ahead of the camera.
	 */
	function repivot() {
		if (Math.hypot(...aim.map((v, i) => v - center[i])) > 0.01) return; // still flying somewhere
		const near = (i: number) => (screen[i].x - frame.cx) ** 2 + (screen[i].y - frame.cy) ** 2;
		const R2 = 90 ** 2;
		let best: number | null = null;
		if (selected !== null && screen[selected].vis && near(selected) < R2) best = selected;
		else
			screen.forEach((s, i) => {
				if (s.vis && near(i) < R2 && (best === null || near(i) < near(best))) best = i;
			});
		if (best === null) return;
		const cam = CAM / Math.sqrt(zoomNow);
		const depth = cam * reach - screen[best].z;
		if (depth < NEAR * 2) return;
		const back = toWorld(0, 0, cam * reach);
		const ahead = toWorld(0, 0, -depth);
		center = center.map((c, k) => c + back[k] + ahead[k]) as Vec;
		aim = [...center];
		reach = reachAim = depth / cam;
	}

	function onDown(e: PointerEvent) {
		touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (touches.size === 2) {
			const [a, b] = [...touches.values()];
			pinch = Math.hypot(a.x - b.x, a.y - b.y);
			drag = null;
			return;
		}
		drag = { x: e.clientX, y: e.clientY, moved: 0 };
		canvas!.setPointerCapture(e.pointerId);
		repivot();
		canvas!.style.cursor = ''; // let the grabbing hand show while dragging
	}
	function onMove(e: PointerEvent) {
		if (touches.has(e.pointerId)) touches.set(e.pointerId, { x: e.clientX, y: e.clientY });
		if (touches.size === 2) {
			const [a, b] = [...touches.values()];
			const d = Math.hypot(a.x - b.x, a.y - b.y);
			if (pinch) zoomBy(d / pinch);
			pinch = d;
			return;
		}
		if (drag) {
			const dx = e.clientX - drag.x;
			const dy = e.clientY - drag.y;
			drag = { x: e.clientX, y: e.clientY, moved: drag.moved + Math.abs(dx) + Math.abs(dy) };
			if (drag.moved > 4) {
				playing = false;
				hover = null;
				tip = null;
				yaw += dx * 0.008;
				pitch = Math.max(-1.4, Math.min(1.4, pitch + dy * 0.008));
				dirty = true;
				return;
			}
		}
		if (e.pointerType !== 'mouse') return;
		// A label already names its game, so pointing at one skips the tooltip.
		const onLabel = pickLabel(e);
		hover = onLabel ?? pick(e);
		tip = hover !== null && onLabel === null ? { x: screen[hover].x, y: screen[hover].y } : null;
		// Anything you can click gets a pointer; the grab hand is for dragging empty space.
		canvas!.style.cursor = hover !== null || pickRegion(e) !== null ? 'pointer' : '';
	}
	function onUp(e: PointerEvent) {
		touches.delete(e.pointerId);
		if (touches.size < 2) pinch = 0;
		if (drag && drag.moved <= 4) {
			const i = pickLabel(e) ?? pick(e);
			const r = i === null ? pickRegion(e) : null;
			if (i !== null) select(i);
			else if (r !== null) flyToRegion(r);
		}
		drag = null;
	}
	function onLeave(e: PointerEvent) {
		touches.delete(e.pointerId);
		if (!drag) {
			hover = null;
			tip = null;
		}
	}
	function onWheel(e: WheelEvent) {
		e.preventDefault();
		// Semantic scroll: during the tour, scrolling over the map moves the story on.
		const story = ui.tour ? panel?.querySelector<HTMLElement>('.tour') : null;
		if (story) story.scrollBy({ top: e.deltaY * (e.deltaMode === 1 ? 32 : 1) });
		else zoomBy(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0015)));
	}

	// --- Keyboard: WASD to fly, Q/E down and up, arrows to look, +/- to zoom ---------------------
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const held = new Set<string>();
	let fast = false;
	const FLY = new Set([
		'w',
		'a',
		's',
		'd',
		'q',
		'e',
		'arrowleft',
		'arrowright',
		'arrowup',
		'arrowdown'
	]);

	function mapKeys(e: KeyboardEvent) {
		if (covered || ui.game !== null || ui.palette) return false;
		if (e.ctrlKey || e.metaKey || e.altKey) return false;
		const t = e.target;
		return !(
			t instanceof HTMLElement &&
			(t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))
		);
	}
	function onWinKeyDown(e: KeyboardEvent) {
		if (!mapKeys(e)) return;
		const k = e.key.toLowerCase();
		fast = e.shiftKey;
		if (FLY.has(k)) {
			e.preventDefault();
			if (k.startsWith('arrow') && !held.has(k)) repivot();
			if (!held.has(k) && !e.repeat) move(k, 0.06); // a tap still nudges
			held.add(k);
			playing = false;
		} else if (k === '+' || k === '=') {
			e.preventDefault();
			zoomBy(1.2);
		} else if (k === '-' || k === '_') {
			e.preventDefault();
			zoomBy(1 / 1.2);
		} else if (k === '[' || k === ']') {
			e.preventDefault();
			stepRank(k === ']' ? 1 : -1);
		} else if (
			k === 'escape' &&
			e.target instanceof Node &&
			canvas?.parentElement?.contains(e.target)
		) {
			if (ui.tour) exitTour();
			else if (selected !== null) clearSelection();
		}
	}
	function onWinKeyUp(e: KeyboardEvent) {
		held.delete(e.key.toLowerCase());
		fast = e.shiftKey;
	}
	function onCanvasKey(e: KeyboardEvent) {
		if (e.key === ' ') {
			e.preventDefault();
			playing = !playing;
		}
	}

	/** Apply one key's motion for `dt` seconds. */
	function move(k: string, dt: number) {
		const look = 1.5 * dt;
		if (k === 'arrowleft') yaw -= look;
		else if (k === 'arrowright') yaw += look;
		else if (k === 'arrowup') pitch = Math.max(-1.4, pitch - look);
		else if (k === 'arrowdown') pitch = Math.min(1.4, pitch + look);
		else {
			const dir: Record<string, Vec> = {
				w: [0, 0, -1],
				s: [0, 0, 1],
				a: [-1, 0, 0],
				d: [1, 0, 0],
				q: [0, -1, 0],
				e: [0, 1, 0]
			};
			const v = toWorld(...dir[k]);
			const step = ((fast ? 2.5 : 1) * 0.9 * dt) / Math.sqrt(zoomNow);
			const next = aim.map((a, i) => a + v[i] * step) as Vec;
			const r = Math.hypot(...next);
			const lim = 2.2;
			aim = r > lim ? (next.map((x) => (x * lim) / r) as Vec) : next;
			center = center.map((c, i) => c + (aim[i] - c) * 0.9) as Vec;
		}
		dirty = true;
	}

	/** Zoom toward whatever is in the middle of the view, not the middle of the whole map. */
	function zoomBy(k: number) {
		repivot();
		zoom = Math.max(ZOOM[0], Math.min(ZOOM[1], zoom * k));
	}
	function reset() {
		reachAim = 1;
		yaw = DEFAULT.yaw;
		pitch = DEFAULT.pitch;
		zoom = DEFAULT.zoom;
		aim = [0, 0, 0];
		selected = null;
		dirty = true;
	}

	let announce = $state('');
	/** Fly to a game and list the games most like it. */
	function select(i: number) {
		reachAim = 1;
		selected = i;
		listHover = null;
		ui.hoverGame = null;
		aim = [...pts[i].p];
		zoom = Math.max(zoom, 4);
		playing = false;
		announce = `Showing ${pts[i].g.name} and its ${N_SIMILAR} most similar games`;
		dirty = true;
	}
	// The ranking, walkable on the map: the top-100 list, prev/next on a selection, and [ / ].
	const byRank = pts.map((_, i) => i).sort((a, b) => pts[a].g.rank - pts[b].g.rank);
	const rankPos = $derived(selected === null ? -1 : byRank.indexOf(selected));
	const prevRanked = $derived(rankPos > 0 ? byRank[rankPos - 1] : null);
	const nextRanked = $derived(
		rankPos >= 0 && rankPos < byRank.length - 1 ? byRank[rankPos + 1] : null
	);
	function stepRank(d: 1 | -1) {
		if (selected === null) return select(byRank[0]);
		const i = d > 0 ? nextRanked : prevRanked;
		if (i !== null) select(i);
	}

	/** Leave the selected game and land back on its row in the top-100 list. */
	function backToList() {
		const id = selected !== null ? pts[selected].g.id : null;
		clearSelection();
		tick().then(() => {
			const row = panel?.querySelector<HTMLElement>(`.top100 [data-id="${id}"]`);
			const target = row ?? panel?.querySelector<HTMLElement>('.top100 button');
			target?.scrollIntoView({ block: 'nearest' });
			target?.focus({ preventScroll: true });
		});
	}

	function clearSelection() {
		reachAim = 1;
		selected = null;
		zoom = DEFAULT.zoom;
		aim = [0, 0, 0];
		announce = 'Selection cleared';
		dirty = true;
	}
	function flyToRegion(id: number) {
		reachAim = 1;
		const r = regions.find((x) => x.id === id);
		if (!r) return;
		selected = null;
		aim = [...r.c];
		zoom = Math.max(zoom, 2.6);
		playing = false;
		announce = `Zoomed in on ${r.name}: ${r.n} games`;
		dirty = true;
	}

	// Other components (the game drawer, the palette, the rankings) can ask the map to show a game.
	$effect(() => {
		const id = ui.mapGame;
		if (id === null) return;
		ui.mapGame = null;
		const i = indexById.get(id);
		if (i === undefined) return;
		untrack(() => select(i));
		tick().then(() => selHead?.focus({ preventScroll: true }));
	});

	// The tour sets scenes as the reader scrolls through it.
	function applyScene(s: Scene) {
		reachAim = 1;
		if (s.mode) mode = s.mode;
		if (s.trait) ui.trait = s.trait;
		if (s.game === null) selected = null;
		else if (s.game !== undefined) {
			const i = indexById.get(s.game);
			if (i !== undefined) select(i);
		}
		if (s.aimTrait && s.trait) aim = traitCentre(s.trait);
		else if (s.game === null) aim = [0, 0, 0];
		if (s.zoom !== undefined) zoom = s.zoom;
		playing = (s.spin ?? false) && !prefersReducedMotion.current;
		dirty = true;
	}
	$effect(() => {
		const s = ui.scene;
		if (s) untrack(() => applyScene(s));
	});
	function exitTour() {
		ui.tour = false;
		applyScene({ mode: 'rating', game: null, zoom: 1, spin: true });
		tick().then(() => panel?.querySelector<HTMLElement>('.start')?.focus());
	}

	// --- Search ---------------------------------------------------------------------------------
	let q = $state('');
	let qOpen = $state(false);
	let qActive = $state(0);
	const qResults = $derived.by(() => {
		const s = q.trim().toLowerCase();
		if (s.length < 2) return [];
		const starts = pts.filter((d) => d.g.name.toLowerCase().startsWith(s));
		const has = pts.filter(
			(d) => !d.g.name.toLowerCase().startsWith(s) && d.g.name.toLowerCase().includes(s)
		);
		return [...starts, ...has].slice(0, 8).map((d) => indexById.get(d.g.id)!);
	});
	// A match outside the mapped top 1,000 gets a hint instead of silence.
	const qOutside = $derived.by(() => {
		const s = q.trim().toLowerCase();
		if (s.length < 2 || qResults.length) return null;
		return data.games.find((g) => !g.umap && g.name.toLowerCase().includes(s)) ?? null;
	});
	function choose(i: number) {
		select(i);
		q = '';
		qOpen = false;
	}
	function onSearchKey(e: KeyboardEvent) {
		const n = qResults.length;
		if (e.key === 'ArrowDown' && n) {
			e.preventDefault();
			qOpen = true;
			qActive = (qActive + 1) % n;
		} else if (e.key === 'ArrowUp' && n) {
			e.preventDefault();
			qActive = (qActive - 1 + n) % n;
		} else if (e.key === 'Enter' && n) {
			e.preventDefault();
			choose(qResults[qActive]);
		} else if (e.key === 'Escape') {
			if (qOpen && n) {
				e.preventDefault();
				qOpen = false;
			} else if (q) q = '';
		}
	}
	const pct = (x: number) => `${Math.round(x * 100)}%`;
	const nameOfTrait = (k: number) => data.traits[k]?.name ?? '';

	// --- Lifecycle ------------------------------------------------------------------------------
	onMount(() => {
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
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
		canvas!.addEventListener('wheel', onWheel, { passive: false });
		const clear = () => held.clear();
		window.addEventListener('blur', clear);

		let raf = 0;
		let last = performance.now();
		const tickFrame = (now: number) => {
			const raw = (now - last) / 1000;
			const dt = Math.min(0.064, raw); // cap steps after a stall
			last = now;
			if (!covered && !document.hidden) {
				if (intro < 1) {
					intro = Math.min(1, intro + Math.min(0.25, raw) / 1.6);
					dirty = true;
				}
				for (const k of held) move(k, dt);
				if (playing && !drag) {
					yaw += dt * 0.12;
					dirty = true;
				}
				// Ease the camera toward its aim and zoom.
				const k = prefersReducedMotion.current ? 1 : 1 - Math.exp(-raw * 5);
				const dc = Math.hypot(...aim.map((v, i) => v - center[i]));
				if (dc > 1e-4 || Math.abs(zoom - zoomNow) > 1e-3 || Math.abs(reachAim - reach) > 1e-3) {
					center = center.map((v, i) => v + (aim[i] - v) * k) as Vec;
					zoomNow += (zoom - zoomNow) * k;
					reach += (reachAim - reach) * k;
					dirty = true;
				}
				if (dirty) {
					dirty = false;
					draw();
					// Keep an open tooltip pinned to its moving dot.
					if (hover !== null && tip)
						tip = screen[hover].vis ? { x: screen[hover].x, y: screen[hover].y } : null;
				}
			}
			raf = requestAnimationFrame(tickFrame);
		};
		raf = requestAnimationFrame(tickFrame);
		return () => {
			cancelAnimationFrame(raf);
			mo.disconnect();
			mq.removeEventListener('change', readPalette);
			canvas?.removeEventListener('wheel', onWheel);
			window.removeEventListener('blur', clear);
		};
	});
</script>

<svelte:window onkeydown={onWinKeyDown} onkeyup={onWinKeyUp} />

<section
	id="space"
	class="space"
	aria-label="3D map of the top {pts.length} games"
	bind:clientWidth={width}
	bind:clientHeight={height}
	inert={covered}
>
	<canvas
		bind:this={canvas}
		style:width="{width}px"
		style:height="{height}px"
		class:grabbing={drag !== null}
		tabindex="0"
		aria-roledescription="3D scatter plot"
		aria-label="3D map of the top {pts.length} games, placed by shared categories and mechanics. W A S D fly, Q and E move down and up, arrow keys look around, plus and minus zoom, space pauses the rotation. Use the search box in the panel to fly to a game."
		onpointerdown={onDown}
		onpointermove={onMove}
		onpointerup={onUp}
		onpointercancel={onUp}
		onpointerleave={onLeave}
		onkeydown={onCanvasKey}
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

	<div class="hud hud-colour">
		<div class="seg" role="group" aria-label="Colour points by">
			<span class="lbl">Colour by</span>
			<button class="chip" aria-pressed={mode === 'rating'} onclick={() => (mode = 'rating')}
				>Rating</button
			>
			<button class="chip" aria-pressed={mode === 'year'} onclick={() => (mode = 'year')}
				>Year</button
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
		<ul class="legend">
			{#if mode === 'rating'}
				<li class="scale">
					<span>{RATING.lo.toFixed(1)}</span>
					<span class="bar rating" aria-hidden="true"></span>
					<span>{RATING.hi.toFixed(1)}+</span>
				</li>
				<li><span class="swatch dot" style:background="var(--series-2)"></span>8.0 and up</li>
			{:else if mode === 'year'}
				<li class="scale">
					<span>{YEAR.lo}</span>
					<span class="bar year" aria-hidden="true"></span>
					<span>{YEAR.hi}</span>
				</li>
				<li>
					<span class="swatch dot recent"></span>{YEAR.recent}
				</li>
				<li>
					<span class="swatch dot newest"></span><strong>{YEAR.newest}+</strong> ({newestCount}
					{newestCount === 1 ? 'game' : 'games'})
				</li>
			{:else}
				<li>
					<span class="swatch dot" style:background="var(--series-1)"></span>{traitName} ({traitCount})
				</li>
				<li><span class="swatch dot" style:background="var(--neutral-dot)"></span>Other games</li>
			{/if}
			<li class="ttl">Dot size = number of ratings</li>
		</ul>
	</div>

	<div class="hud hud-view">
		<div class="view" role="group" aria-label="View controls">
			<button class="chip" aria-pressed={playing} onclick={() => (playing = !playing)}>
				{playing ? 'Pause' : 'Rotate'}
			</button>
			<button class="chip icon" aria-label="Zoom in" onclick={() => zoomBy(1.3)}>+</button>
			<button class="chip icon" aria-label="Zoom out" onclick={() => zoomBy(1 / 1.3)}>−</button>
			<button class="chip" onclick={reset}>Reset</button>
		</div>
		<p class="keys">
			<kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> fly · <kbd>Q</kbd><kbd>E</kbd> down/up · drag
			to look · scroll to zoom · <kbd>Shift</kbd> faster · <kbd>[</kbd><kbd>]</kbd> step through the ranking
		</p>
	</div>

	<aside class="panel" class:touring={ui.tour} bind:this={panel} aria-label="Map panel">
		{#if ui.tour}
			<Tour onexit={exitTour} />
		{:else}
			{#if returnTo}
				<button class="back" onclick={backToChapter}>← Back to {returnTo.label}</button>
			{/if}
			<div class="search">
				<label for="umap-search" class="panel-title">Fly to a game</label>
				<input
					id="umap-search"
					type="search"
					placeholder="Search the top {pts.length}…"
					autocomplete="off"
					role="combobox"
					aria-expanded={qOpen && qResults.length > 0}
					aria-controls="umap-search-list"
					aria-autocomplete="list"
					aria-activedescendant={qOpen && qResults.length
						? `umap-opt-${pts[qResults[qActive]]?.g.id}`
						: undefined}
					bind:value={q}
					oninput={() => {
						qOpen = true;
						qActive = 0;
					}}
					onfocus={() => (qOpen = true)}
					onblur={() => setTimeout(() => (qOpen = false), 150)}
					onkeydown={onSearchKey}
				/>
				{#if qOpen && qResults.length}
					<ul id="umap-search-list" role="listbox" aria-label="Matching games">
						{#each qResults as i, k (pts[i].g.id)}
							<li
								id="umap-opt-{pts[i].g.id}"
								role="option"
								aria-selected={k === qActive}
								onmousedown={(e) => {
									e.preventDefault();
									choose(i);
								}}
								onmouseenter={() => (qActive = k)}
							>
								<span class="nm">{pts[i].g.name}</span>
								<span class="meta">#{pts[i].g.rank} · {pts[i].g.year}</span>
							</li>
						{/each}
					</ul>
				{:else if qOutside}
					<p class="hint">
						{qOutside.name} is #{qOutside.rank}, outside the top {pts.length} on this map.
						<button class="inline" onclick={() => openGame(qOutside!.id)}>Open its details</button>
					</p>
				{/if}
			</div>

			{#if selectedGame && selected !== null}
				<button class="backlist" onclick={backToList}>← Back to the top 100</button>
				<div class="sel">
					<h2 class="sel-name" tabindex="-1" bind:this={selHead}>{selectedGame.name}</h2>
					<p class="sel-meta">
						#{selectedGame.rank} · {selectedGame.year} · rated {fmt.r2(selectedGame.rating)}
					</p>
					<div class="sel-actions">
						<button class="chip" onclick={() => openGame(selectedGame.id)}>Details</button>
						<button class="chip" onclick={clearSelection}>Clear</button>
					</div>
					<div class="ranknav" role="group" aria-label="Step through the ranking">
						{#if prevRanked !== null}
							<button class="chip" onclick={() => stepRank(-1)} aria-keyshortcuts="["
								>← #{pts[prevRanked].g.rank}<span class="visually-hidden">
									{pts[prevRanked].g.name}, previous in the ranking</span
								></button
							>
						{/if}
						{#if nextRanked !== null}
							<button class="chip" onclick={() => stepRank(1)} aria-keyshortcuts="]"
								>#{pts[nextRanked].g.rank}<span class="visually-hidden">
									{pts[nextRanked].g.name}, next in the ranking</span
								> →</button
							>
						{/if}
					</div>
				</div>
				<h3 class="panel-sub">Most similar games</h3>
				<ol class="similar">
					{#each similar as s (pts[s.i].g.id)}
						{@const g = pts[s.i].g}
						<li>
							<button
								class="sim"
								onclick={() => select(s.i)}
								onpointerenter={() => (listHover = s.i)}
								onpointerleave={() => (listHover = null)}
								onfocus={() => (listHover = s.i)}
								onblur={() => (listHover = null)}
							>
								<span class="sim-top">
									<span class="sim-name">{g.name}</span>
									<span class="sim-pct">{pct(s.sim)}</span>
								</span>
								<span class="sim-bar"><span style:width={pct(s.sim)}></span></span>
								<span class="sim-meta">
									#{g.rank} · {fmt.r2(g.rating)} · shares {s.common.length}:
									{s.common.slice(0, 3).map(nameOfTrait).join(', ')}{s.common.length > 3 ? '…' : ''}
								</span>
							</button>
						</li>
					{/each}
				</ol>
				<p class="panel-note">
					Similarity is the share of categories and mechanics two games have in common (Jaccard),
					the same measure the map is built from. Pick one to fly to it.
				</p>
			{:else}
				<div class="intro">
					<p class="eyebrow">BoardGameGeek top {pts.length} · {snapshot}</p>
					<p class="lede">
						Every dot is a board game. Games that share categories and mechanics sit close together,
						so the clumps are genres. Zoom in and the map tells you more.
					</p>
					<div class="ctas">
						<button class="cta start" onclick={() => (ui.tour = true)}>Take the tour</button>
						<button class="chip" onclick={() => openChapter('overview')}>Read the analysis</button>
					</div>
				</div>
				<h2 class="panel-sub" id="top100-h">Top 100</h2>
				<ol class="top100" aria-labelledby="top100-h">
					{#each byRank.slice(0, 100) as i (pts[i].g.id)}
						{@const g = pts[i].g}
						<li>
							<button
								data-id={g.id}
								onclick={() => select(i)}
								onpointerenter={() => (ui.hoverGame = g.id)}
								onpointerleave={() => (ui.hoverGame = null)}
								><span class="rk">{g.rank}</span><span class="nm">{g.name}</span><span class="rt"
									>{fmt.r2(g.rating)}</span
								></button
							>
						</li>
					{/each}
				</ol>
				<h2 class="panel-sub">Regions</h2>
				<div class="examples" role="group" aria-label="Fly to a region">
					{#each regions.slice(0, 8) as r (r.id)}
						<button class="chip" onclick={() => flyToRegion(r.id)}>{r.traits[0]}</button>
					{/each}
				</div>
				<h2 class="panel-sub">Chapters</h2>
				<ol class="toc">
					{#each chapters as c, i (c.id)}
						<li>
							<a
								href={chapterHref(c.id)}
								onclick={(e) => {
									e.preventDefault();
									openChapter(c.id, e.currentTarget);
								}}><span class="n">{String(i + 1).padStart(2, '0')}</span>{c.label}</a
							>
						</li>
					{/each}
				</ol>
			{/if}
			<details class="table-view">
				<summary>Table view: each game’s nearest neighbours</summary>
				<div class="scroll">
					<table>
						<thead><tr><th>Rank</th><th>Game</th><th>Closest on the map</th></tr></thead>
						<tbody>
							{#each pts as d (d.g.id)}
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
		{/if}
		<div class="visually-hidden" role="status" aria-live="polite">{announce}</div>
	</aside>
</section>

<style>
	.space {
		position: fixed;
		inset: 0;
		overflow: hidden;
		background: var(--page);
	}
	canvas {
		position: absolute;
		inset: 0;
		display: block;
		cursor: grab;
		touch-action: none;
	}
	canvas.grabbing {
		cursor: grabbing;
	}
	canvas:focus-visible {
		outline-offset: -4px;
	}
	.hud {
		position: absolute;
		background: color-mix(in srgb, var(--surface-1) 92%, transparent);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 0.5rem 0.65rem;
		font-size: 0.82rem;
		box-shadow: var(--shadow);
	}
	.hud-colour {
		top: calc(56px + 0.75rem);
		right: 0.75rem;
		max-width: min(560px, calc(100vw - 344px - 2rem));
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.75rem;
	}
	.hud-view {
		right: 0.75rem;
		bottom: 0.75rem;
		display: grid;
		gap: 0.35rem;
		justify-items: end;
	}
	.seg,
	.view {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
	}
	.lbl,
	.ttl {
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 0.7rem;
		list-style: none;
		margin: 0;
		padding: 0;
		color: var(--text-secondary);
		font-size: 0.78rem;
	}
	.legend li {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.scale {
		gap: 0.35rem;
	}
	.bar {
		display: inline-block;
		width: 96px;
		height: 8px;
		border-radius: 4px;
	}
	/* Same stops as the canvas: RATING.lo 6.9 → 7.99 cool, 8.0 → 8.7 warm (8.0 sits at 61%). */
	.bar.rating {
		background: linear-gradient(
			90deg,
			var(--ord-1) 0%,
			var(--ord-4) 60.5%,
			var(--series-2) 61%,
			var(--div-neg) 100%
		);
	}
	.bar.year {
		background: linear-gradient(90deg, var(--ord-1), var(--ord-5));
	}
	.swatch.recent {
		background: color-mix(in lab, var(--series-2) 55%, var(--surface-1));
	}
	.swatch.newest {
		background: var(--series-2);
		box-shadow: 0 0 0 1.5px var(--text-primary);
	}
	.keys {
		margin: 0;
		color: var(--text-muted);
		font-size: 0.75rem;
	}
	.keys kbd {
		font: inherit;
		font-size: 0.7rem;
		border: 1px solid var(--border);
		border-bottom-width: 2px;
		border-radius: 4px;
		padding: 0 0.25rem;
		margin-right: 1px;
		color: var(--text-secondary);
		background: var(--surface-1);
	}
	.icon {
		width: 2rem;
		padding: 0.25rem 0;
		text-align: center;
	}
	select {
		max-width: 220px;
		border: 1px solid var(--border);
		background: var(--surface-1);
		border-radius: 8px;
		padding: 0.3rem 0.5rem;
		font-size: 0.85rem;
	}
	.panel {
		position: absolute;
		top: calc(56px + 0.75rem);
		left: 0.75rem;
		bottom: 0.75rem;
		width: 320px;
		overflow-y: auto;
		background: color-mix(in srgb, var(--surface-1) 95%, transparent);
		border: 1px solid var(--border);
		border-radius: 14px;
		padding: 0.9rem;
		font-size: 0.88rem;
		box-shadow: var(--shadow);
	}
	.panel.touring {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		padding: 0;
	}
	@media (max-width: 859px) {
		.panel {
			top: auto;
			left: 0;
			right: 0;
			bottom: 0;
			width: auto;
			height: 44dvh;
			border-radius: 16px 16px 0 0;
			border-bottom: 0;
		}
		.hud-colour {
			top: calc(56px + 0.4rem);
			left: 0.5rem;
			right: 0.5rem;
			max-width: none;
			padding: 0.35rem 0.5rem;
		}
		.hud-colour .legend {
			display: none;
		}
		.hud-view {
			right: 0.5rem;
			bottom: calc(44dvh + 0.5rem);
			padding: 0.3rem;
		}
		.keys {
			display: none;
		}
	}
	.back {
		display: block;
		width: 100%;
		margin-bottom: 0.75rem;
		padding: 0.5rem 0.7rem;
		border-radius: 10px;
		border: 1px solid var(--series-1);
		background: var(--surface-2);
		color: var(--text-primary);
		font-weight: 600;
		text-align: left;
		cursor: pointer;
	}
	.intro {
		margin: 0.9rem 0 0.4rem;
	}
	.intro .eyebrow {
		margin-bottom: 0.3rem;
	}
	.lede {
		color: var(--text-secondary);
		margin: 0 0 0.75rem;
		line-height: 1.45;
	}
	.ctas {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.cta {
		border: 0;
		border-radius: 999px;
		padding: 0.4rem 0.95rem;
		font-weight: 600;
		font-size: 0.88rem;
		background: var(--text-primary);
		color: var(--surface-1);
		cursor: pointer;
	}
	.toc {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
	}
	.toc a {
		display: flex;
		gap: 0.6rem;
		padding: 0.3rem 0.4rem;
		border-radius: 6px;
		color: var(--text-primary);
		text-decoration: none;
	}
	.toc a:hover {
		background: var(--surface-2);
	}
	.toc .n {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.panel-title {
		display: block;
		font-weight: 600;
		color: var(--text-primary);
		margin-bottom: 0.4rem;
	}
	.search {
		position: relative;
	}
	.search input {
		width: 100%;
		border: 1px solid var(--border);
		background: var(--page);
		border-radius: 8px;
		padding: 0.45rem 0.6rem;
		font-size: 0.9rem;
		min-height: 36px;
	}
	.search ul {
		position: absolute;
		z-index: 5;
		left: 0;
		right: 0;
		top: 100%;
		margin: 0.25rem 0 0;
		padding: 0.25rem;
		list-style: none;
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: var(--shadow);
	}
	.search li {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.4rem 0.5rem;
		border-radius: 6px;
		cursor: pointer;
		color: var(--text-primary);
	}
	.search li[aria-selected='true'] {
		background: var(--surface-2);
		box-shadow: inset 3px 0 0 var(--series-1);
	}
	.search .meta,
	.sim-meta,
	.sel-meta,
	.panel-note,
	.hint {
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	.hint {
		margin: 0.5rem 0 0;
	}
	.inline {
		background: none;
		border: 0;
		padding: 0;
		color: var(--link);
		text-decoration: underline;
		cursor: pointer;
		font-size: inherit;
	}
	.sel {
		margin: 0.9rem 0 0.6rem;
		padding-bottom: 0.7rem;
		border-bottom: 1px solid var(--border);
	}
	.sel-name {
		font-weight: 650;
		font-size: 1.05rem;
		color: var(--text-primary);
		margin: 0;
		line-height: 1.25;
		letter-spacing: normal;
	}
	.sel-meta {
		margin: 0.15rem 0 0.5rem;
	}
	.sel-actions {
		display: flex;
		gap: 0.35rem;
	}
	.panel-sub {
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-muted);
		margin: 1rem 0 0.4rem;
	}
	.similar {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.sim {
		display: grid;
		gap: 0.2rem;
		width: 100%;
		text-align: left;
		background: none;
		border: 0;
		border-radius: 8px;
		padding: 0.45rem 0.5rem;
		cursor: pointer;
	}
	.sim:hover,
	.sim:focus-visible {
		background: var(--surface-2);
	}
	.sim-top {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.sim-name {
		color: var(--text-primary);
		font-weight: 550;
	}
	.sim-pct {
		color: var(--text-secondary);
		font-variant-numeric: tabular-nums;
	}
	.sim-bar {
		height: 4px;
		border-radius: 2px;
		background: var(--surface-2);
		overflow: hidden;
	}
	.sim-bar span {
		display: block;
		height: 100%;
		background: var(--series-1);
		border-radius: 2px;
	}
	.backlist {
		display: block;
		margin: 0.75rem 0 0;
		padding: 0.25rem 0;
		border: 0;
		background: none;
		color: var(--link);
		font-size: 0.85rem;
		font-weight: 600;
		cursor: pointer;
	}
	.backlist:hover {
		text-decoration: underline;
	}
	.ranknav {
		display: flex;
		justify-content: space-between;
		gap: 0.35rem;
		margin-top: 0.5rem;
	}
	.ranknav .chip:only-child:last-child {
		margin-left: auto;
	}
	.top100 {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 260px;
		overflow-y: auto;
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.top100 button {
		display: grid;
		grid-template-columns: 2.1rem minmax(0, 1fr) auto;
		gap: 0.4rem;
		width: 100%;
		padding: 0.3rem 0.55rem;
		border: 0;
		background: none;
		text-align: left;
		cursor: pointer;
		color: var(--text-primary);
		font-size: 0.84rem;
	}
	.top100 button:hover,
	.top100 button:focus-visible {
		background: var(--surface-2);
	}
	.top100 .rk,
	.top100 .rt {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.top100 .nm {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.examples {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.near {
		margin-top: 0.25rem;
		color: var(--text-muted);
	}
	.table-view {
		margin-top: 1.25rem;
		font-size: 0.8rem;
	}
	.table-view summary {
		cursor: pointer;
		color: var(--text-secondary);
	}
	.table-view .scroll {
		max-height: 320px;
		overflow: auto;
		margin-top: 0.5rem;
	}
	.table-view table {
		border-collapse: collapse;
		width: 100%;
	}
	.table-view th,
	.table-view td {
		text-align: left;
		padding: 0.25rem 0.35rem;
		border-bottom: 1px solid var(--grid);
		vertical-align: top;
	}
</style>
