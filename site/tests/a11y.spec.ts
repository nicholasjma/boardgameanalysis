import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { load, textContrast, themes } from './helpers';

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'];
const CHAPTERS = [
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

for (const theme of themes) {
	test.describe(`${theme} theme`, () => {
		test('axe finds no WCAG 2.2 AA violations on the map', async ({ page }) => {
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

		test('every chapter pane passes axe and text contrast', async ({ page }) => {
			// Each pane holds a few thousand chart marks; nine of them take a while on a CI runner.
			test.setTimeout(240_000);
			await load(page, theme);
			for (const id of CHAPTERS) {
				await page.evaluate((h) => (location.hash = h), id);
				const pane = page.locator('section.pane');
				if (!(await pane.count())) continue; // e.g. no 2018 snapshot at build time
				await expect(pane.getByRole('heading', { level: 2 }).first()).toBeFocused();
				await page.waitForTimeout(400);
				const res = await new AxeBuilder({ page }).include('section.pane').withTags(WCAG).analyze();
				const summary = res.violations.map((v) => ({
					chapter: id,
					rule: v.id,
					nodes: v.nodes.slice(0, 5).map((n) => n.target.join(' ')),
					count: v.nodes.length
				}));
				expect(summary).toEqual([]);
				expect((await textContrast(page)).map((f) => ({ chapter: id, ...f }))).toEqual([]);
			}
		});

		test('the guided tour passes axe and contrast', async ({ page }) => {
			await load(page, theme);
			await page.getByRole('button', { name: 'Take the tour' }).click();
			await expect(page.getByRole('heading', { name: 'Guided tour' })).toBeFocused();
			const res = await new AxeBuilder({ page }).include('#space').withTags(WCAG).analyze();
			expect(res.violations.map((v) => v.id)).toEqual([]);
			expect(await textContrast(page)).toEqual([]);
		});

		test('axe passes with the game drawer and command palette open', async ({ page }) => {
			test.setTimeout(60_000);
			await load(page, theme);
			await page.getByRole('button', { name: /search and commands/i }).click();
			await expect(page.getByRole('dialog', { name: 'Command menu' })).toBeVisible();
			let res = await new AxeBuilder({ page }).include('[role="dialog"]').withTags(WCAG).analyze();
			expect(res.violations.map((v) => v.id)).toEqual([]);

			await page.keyboard.type('Brass');
			await page.keyboard.press('Shift+Enter'); // details; plain Enter flies the map
			await expect(page.getByRole('dialog', { name: /Brass/ })).toBeVisible();
			res = await new AxeBuilder({ page }).include('[role="dialog"]').withTags(WCAG).analyze();
			expect(res.violations.map((v) => v.id)).toEqual([]);
		});

		test('3D map panel with a game selected passes axe and contrast', async ({ page }) => {
			await load(page, theme);
			await page.getByRole('combobox', { name: 'Fly to a game' }).fill('Brass');
			await page.getByRole('combobox', { name: 'Fly to a game' }).press('Enter');
			await expect(page.locator('#space .sim')).toHaveCount(10);
			const res = await new AxeBuilder({ page }).include('#space').withTags(WCAG).analyze();
			expect(res.violations.map((v) => v.id)).toEqual([]);
			expect(await textContrast(page)).toEqual([]);
		});

		test('all visible text on the map meets WCAG contrast', async ({ page }) => {
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
