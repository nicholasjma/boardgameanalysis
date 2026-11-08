/**
 * The 3D map is home. Everything else is a chapter that opens as a pane over it; the id doubles
 * as the URL hash (#recipe), so chapters can be linked to and the back button closes them.
 */
import { data } from '#lib/data.ts';

export type Chapter = { id: string; label: string; title: string };

const all: readonly Chapter[] = [
	{ id: 'overview', label: 'Overview', title: 'What’s in a rating?' },
	{ id: 'recipe', label: 'The recipe', title: 'Newer and longer wins, then the details' },
	{ id: 'prediction', label: 'Predicted vs actual', title: 'Traits get you most of the way' },
	{ id: 'magic', label: 'Magic sauce', title: 'What the traits can’t explain' },
	{ id: 'traits', label: 'Trait explorer', title: 'Pick a mechanic or category' },
	{ id: 'map', label: 'Game families', title: 'The top 500, grouped by what they share' },
	{ id: 'change', label: 'Since 2018', title: 'Seven years of the BGG top list' },
	{ id: 'games', label: 'All games', title: 'Every game, every number' },
	{ id: 'methods', label: 'Methods', title: 'Method and data' }
];

/** The 2018 comparison only exists when that snapshot was available at build time. */
export const chapters = all.filter((c) => c.id !== 'change' || data.compare);

export const chapterById = new Map(chapters.map((c) => [c.id, c]));

/**
 * A chapter's link, relative to the page (the site always lives at a directory URL, so this is
 * the same page in dev and on GitHub Pages). Not a bare `#recipe`: the hash names a pane, not
 * an element, and links of that form are what screen-reader tools treat as skip links.
 */
export const chapterHref = (id: string) => `./#${id}`;
