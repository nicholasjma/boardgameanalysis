import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { load, textContrast, themes } from './helpers';

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];

for (const theme of themes) {
	test.describe(`${theme} theme`, () => {
		test('axe finds no WCAG 2.2 AA violations', async ({ page }) => {
			// A full scan visits ~13k chart marks: ~10 s locally, ~28 s on a CI runner.
			test.setTimeout(120_000);
			await load(page, theme);
			const { violations } = await new AxeBuilder({ page }).withTags(WCAG).analyze();
			const summary = violations.map((v) => ({
				rule: v.id,
				impact: v.impact,
				nodes: v.nodes.slice(0, 5).map((n) => n.target.join(' ')),
				count: v.nodes.length
			}));
			expect(summary).toEqual([]);
		});

		test('axe passes with the game drawer and command palette open', async ({ page }) => {
			test.setTimeout(60_000);
			await load(page, theme);
			await page.getByRole('button', { name: /search and commands/i }).click();
			await expect(page.getByRole('dialog', { name: 'Command menu' })).toBeVisible();
			let res = await new AxeBuilder({ page }).include('[role="dialog"]').withTags(WCAG).analyze();
			expect(res.violations.map((v) => v.id)).toEqual([]);

			await page.keyboard.type('Brass');
			await page.keyboard.press('Enter');
			await expect(page.getByRole('dialog', { name: /Brass/ })).toBeVisible();
			res = await new AxeBuilder({ page }).include('[role="dialog"]').withTags(WCAG).analyze();
			expect(res.violations.map((v) => v.id)).toEqual([]);
		});

		test('all visible text, including chart labels, meets WCAG contrast', async ({ page }) => {
			await load(page, theme);
			expect(await textContrast(page)).toEqual([]);
		});

		test('colour tokens meet their contrast targets', async ({ page }) => {
			await load(page, theme);
			const failures = await page.evaluate(() => {
				const cs = getComputedStyle(document.documentElement);
				const v = (n: string) => cs.getPropertyValue(n).trim();
				const ctx = document
					.createElement('canvas')
					.getContext('2d', { willReadFrequently: true })!;
				const lum = (css: string) => {
					ctx.clearRect(0, 0, 1, 1);
					ctx.fillStyle = css;
					ctx.fillRect(0, 0, 1, 1);
					const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
					const f = (x: number) =>
						(x /= 255) <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
					return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
				};
				const ratio = (a: string, b: string) => {
					const [x, y] = [lum(a), lum(b)];
					return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
				};
				const surfaces = ['--page', '--surface-1', '--surface-2'];
				// Text tokens need 4.5:1 (1.4.3); the focus ring and selection accents need 3:1 (1.4.11).
				const rules: [string, number][] = [
					['--text-primary', 4.5],
					['--text-secondary', 4.5],
					['--text-muted', 4.5],
					['--series-1', 3]
				];
				const out: string[] = [];
				for (const [fg, need] of rules)
					for (const bg of surfaces) {
						const r = ratio(v(fg), v(bg));
						if (r < need) out.push(`${fg} on ${bg}: ${r.toFixed(2)} < ${need}`);
					}
				return out;
			});
			expect(failures).toEqual([]);
		});
	});
}
