import type { Action } from 'svelte/action';

/** Calls `onEnter` once, the first time the element scrolls into view. */
export const inview: Action<HTMLElement, () => void> = (node, onEnter) => {
	if (typeof IntersectionObserver === 'undefined') {
		onEnter?.();
		return;
	}
	const io = new IntersectionObserver(
		(entries) => {
			if (entries.some((e) => e.isIntersecting)) {
				onEnter?.();
				io.disconnect();
			}
		},
		{ threshold: 0.25 }
	);
	io.observe(node);
	return { destroy: () => io.disconnect() };
};
