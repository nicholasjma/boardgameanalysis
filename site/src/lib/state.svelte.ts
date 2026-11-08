import { prefersReducedMotion } from 'svelte/motion';

export type Theme = 'light' | 'dark';

/** Cross-chart selection and app chrome state. */
export const ui = $state({
	game: null as number | null,
	trait: 'mech:Cooperative Game' as string,
	hoverGame: null as number | null,
	palette: false,
	theme: 'light' as Theme
});

// Where focus was before a dialog opened, so closing it can put focus back.
let gameOpener: HTMLElement | null = null;

export function openGame(id: number) {
	if (ui.game === null && typeof document !== 'undefined') {
		const a = document.activeElement;
		// Opened from the palette: return to whatever opened the palette instead.
		if (a instanceof HTMLElement && !a.closest('[data-palette]')) gameOpener = a;
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

/** Scroll to a section and move keyboard focus to its heading. */
export function goToSection(id: string) {
	const section = document.getElementById(id);
	if (!section) return;
	section.scrollIntoView({ behavior: scrollBehavior() });
	const heading = section.querySelector<HTMLElement>('h1, h2') ?? section;
	heading.setAttribute('tabindex', '-1');
	heading.focus({ preventScroll: true });
	history.replaceState(null, '', `#${id}`);
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
