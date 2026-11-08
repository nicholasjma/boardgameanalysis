import { prefersReducedMotion } from 'svelte/motion';
import { chapterById } from '#lib/chapters.ts';

export type Theme = 'light' | 'dark';
export type MapMode = 'rating' | 'year' | 'trait';

/**
 * A view the guided tour asks the 3D map to show. Every field is optional: what is left out
 * stays as it is.
 */
export type Scene = {
	mode?: MapMode;
	trait?: string;
	/** Game id to fly to and select; null clears the selection. */
	game?: number | null;
	/** Fly to the middle of the games that have `trait`. */
	aimTrait?: boolean;
	zoom?: number;
	spin?: boolean;
};

/** Cross-chart selection and app chrome state. */
export const ui = $state({
	game: null as number | null,
	trait: 'mech:Cooperative Game' as string,
	hoverGame: null as number | null,
	palette: false,
	/** A game another component asked the 3D map to fly to; the map consumes and clears it. */
	mapGame: null as number | null,
	/** The chapter open over the map, if any. */
	pane: null as string | null,
	/** The chapter is tucked away while the reader looks at something on the map. */
	paneHidden: false,
	/** The guided tour is running in the map's side panel. */
	tour: false,
	scene: null as Scene | null,
	theme: 'light' as Theme
});

// Where focus was before a dialog opened, so closing it can put focus back.
let gameOpener: HTMLElement | null = null;
let paneOpener: HTMLElement | null = null;
let paneReturn: HTMLElement | null = null;

const active = () =>
	typeof document !== 'undefined' && document.activeElement instanceof HTMLElement
		? document.activeElement
		: null;
const refocus = (el: HTMLElement | null) => {
	if (el?.isConnected) setTimeout(() => el.focus({ preventScroll: true }));
};

export function openGame(id: number) {
	if (ui.game === null) {
		const a = active();
		// Opened from the palette: return to whatever opened the palette instead.
		if (a && !a.closest('[data-palette]')) gameOpener = a;
	}
	ui.game = id;
}

export function closeGame() {
	ui.game = null;
	const el = gameOpener;
	gameOpener = null;
	if (el?.isConnected) queueMicrotask(() => el.focus({ preventScroll: true }));
}

/** Hand focus back to the palette's opener once a game it opened is closed. */
export function setGameOpener(el: HTMLElement | null) {
	gameOpener = el;
}

export const scrollBehavior = (): ScrollBehavior =>
	prefersReducedMotion.current ? 'auto' : 'smooth';

/** Open a chapter over the map. Its heading takes focus once it renders. */
export function openChapter(id: string, opener: HTMLElement | null = active()) {
	if (!chapterById.has(id)) return closeChapter();
	if (ui.pane === null || ui.paneHidden)
		paneOpener = opener?.closest('[data-pane]') ? null : opener;
	ui.game = null;
	ui.pane = id;
	ui.paneHidden = false;
	paneReturn = null;
	if (location.hash !== `#${id}`) history.pushState(null, '', `#${id}`);
}

/** Close the chapter and go back to the map. */
export function closeChapter() {
	const had = ui.pane !== null;
	ui.pane = null;
	ui.paneHidden = false;
	paneReturn = null;
	if (location.hash) history.pushState(null, '', location.pathname + location.search);
	if (had) {
		const el = paneOpener;
		paneOpener = null;
		// The opener can be gone (say, the map panel now shows a game): land on the map instead.
		refocus(
			el?.isConnected
				? el
				: (document.querySelector<HTMLElement>('#space .sel-name') ??
						document.querySelector<HTMLElement>('#space canvas'))
		);
	}
}

/** Follow the URL hash (initial load, back and forward buttons). */
export function syncChapterFromHash() {
	const id = location.hash.slice(1);
	ui.pane = chapterById.has(id) ? id : null;
	ui.paneHidden = false;
	paneReturn = null;
}

/** Old in-page links (#top, #space) now mean the map; chapter ids open their pane. */
export function goToSection(id: string) {
	if (chapterById.has(id)) openChapter(id);
	else closeChapter();
}

/**
 * Show a game on the 3D map. Called from a chapter, the chapter steps aside rather than
 * closing, so the map's panel can offer a way straight back to where the reader was.
 */
export function flyTo(id: number) {
	let from = active();
	if (ui.game !== null) {
		ui.game = null;
		from = gameOpener;
		gameOpener = null;
	}
	if (ui.pane !== null && !ui.paneHidden) {
		ui.paneHidden = true;
		paneReturn = from;
	}
	ui.tour = false;
	ui.mapGame = id;
}

/** Bring back the chapter that `flyTo` tucked away, with focus where it was. */
export function backToChapter() {
	if (ui.pane === null) return;
	ui.paneHidden = false;
	const el = paneReturn;
	paneReturn = null;
	refocus(el);
}

export function initTheme() {
	const saved = localStorage.getItem('theme');
	ui.theme =
		saved === 'light' || saved === 'dark'
			? saved
			: matchMedia('(prefers-color-scheme: dark)').matches
				? 'dark'
				: 'light';
}

export function toggleTheme() {
	ui.theme = ui.theme === 'dark' ? 'light' : 'dark';
	document.documentElement.dataset.theme = ui.theme;
	localStorage.setItem('theme', ui.theme);
}
