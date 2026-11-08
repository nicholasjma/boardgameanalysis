import type { Action } from 'svelte/action';

/**
 * Render an element at the end of <body>, so fixed-position overlays escape ancestors that
 * create containing blocks (the sticky header's backdrop-filter does).
 */
export const portal: Action<HTMLElement> = (node) => {
	document.body.appendChild(node);
	return { destroy: () => node.remove() };
};
