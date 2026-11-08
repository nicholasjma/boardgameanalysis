import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// GitHub Pages serves project sites from /<repo>; CI sets BASE_PATH=/boardgameanalysis.
const base = (process.env.BASE_PATH ?? '') as '' | `/${string}`;
const chapterIds = [
	'overview',
	'recipe',
	'prediction',
	'magic',
	'traits',
	'map',
	'change',
	'games',
	'methods'
];

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter({ fallback: '404.html' }),
			paths: { base },
			prerender: {
				// Chapter hashes (#recipe) open panes over the map rather than scrolling to an
				// element, so they have no matching id. Keep this list in step with src/lib/chapters.ts.
				handleMissingId: ({ id, message }) => {
					if (!chapterIds.includes(id)) throw new Error(message);
				}
			}
		})
	]
});
