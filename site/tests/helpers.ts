import type { Page } from '@playwright/test';

export type Theme = 'light' | 'dark';
export const themes: Theme[] = ['light', 'dark'];

/**
 * Open the page in a theme with motion reduced, then scroll through it so every chart's
 * scroll-triggered entrance has run and the page is in its resting state.
 */
export async function load(page: Page, theme: Theme, path = '/') {
	await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: theme });
	await page.addInitScript((t) => localStorage.setItem('theme', t), theme);
	await page.goto(path);
	await page.waitForFunction(() => document.querySelector('main svg') !== null);
	await page.evaluate(async () => {
		const step = innerHeight * 0.6;
		for (let y = 0; y < document.body.scrollHeight; y += step) {
			scrollTo(0, y);
			await new Promise((r) => setTimeout(r, 40));
		}
		scrollTo(0, 0);
	});
	await page.waitForTimeout(300);
}

export interface ContrastFailure {
	text: string;
	where: string;
	ratio: number;
	need: number;
}

/**
 * WCAG 1.4.3 check over every visible text run, including SVG chart text (which axe skips).
 * Foreground alpha and ancestor opacity are composited over the nearest opaque backgrounds.
 */
export function textContrast(page: Page): Promise<ContrastFailure[]> {
	return page.evaluate(() => {
		type C = { r: number; g: number; b: number; a: number };
		const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!;
		const rgb = (css: string): C => {
			ctx.clearRect(0, 0, 1, 1);
			ctx.fillStyle = '#000';
			ctx.fillStyle = css;
			ctx.fillRect(0, 0, 1, 1);
			const d = ctx.getImageData(0, 0, 1, 1).data;
			return { r: d[0], g: d[1], b: d[2], a: d[3] / 255 };
		};
		const over = (f: C, b: C): C => ({
			r: f.r * f.a + b.r * (1 - f.a),
			g: f.g * f.a + b.g * (1 - f.a),
			b: f.b * f.a + b.b * (1 - f.a),
			a: 1
		});
		const lum = (c: C) => {
			const f = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
			return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
		};
		const ratio = (a: C, b: C) => {
			const [x, y] = [lum(a), lum(b)];
			return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
		};
		const pageBg = rgb(getComputedStyle(document.documentElement).backgroundColor);
		const base = pageBg.a ? pageBg : rgb(getComputedStyle(document.body).backgroundColor);
		const bgOf = (el: Element) => {
			const layers: C[] = [];
			for (let e: Element | null = el; e; e = e.parentElement) {
				const c = rgb(getComputedStyle(e).backgroundColor);
				if (c.a > 0) layers.push(c);
				if (c.a >= 1) break;
			}
			return layers.reverse().reduce((bg, l) => over(l, bg), { ...base, a: 1 });
		};

		const out: { text: string; where: string; ratio: number; need: number }[] = [];
		const seen = new Set<Element>();
		const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
		while (walker.nextNode()) {
			const node = walker.currentNode;
			const text = node.textContent?.trim();
			const el = node.parentElement;
			if (!text || !el || seen.has(el)) continue;
			seen.add(el);
			// Disabled controls are exempt from 1.4.3.
			if (
				el.closest(
					'[aria-hidden="true"], .visually-hidden, script, style, title, option, :disabled'
				)
			)
				continue;
			const cs = getComputedStyle(el);
			if (cs.visibility === 'hidden' || cs.display === 'none') continue;
			const box = el.getBoundingClientRect();
			if (!box.width || !box.height) continue;
			let op = 1;
			for (let e: Element | null = el; e; e = e.parentElement)
				op *= Number(getComputedStyle(e).opacity);
			if (op < 0.05) continue; // not rendered (yet)
			const isSvg = el instanceof SVGElement;
			const fg = rgb(isSvg ? cs.fill : cs.color);
			const bg = bgOf(el);
			const r = ratio(over({ ...fg, a: fg.a * op }, bg), bg);
			const size = parseFloat(cs.fontSize);
			const large = size >= 24 || (Number(cs.fontWeight) >= 700 && size >= 18.66);
			const need = large ? 3 : 4.5;
			if (r < need) {
				const cls = (el.getAttribute('class') ?? '').replace(/svelte-\w+/g, '').trim();
				out.push({
					text: text.slice(0, 40),
					where: `${el.tagName.toLowerCase()}.${cls}`,
					ratio: +r.toFixed(2),
					need
				});
			}
		}
		return out;
	});
}
