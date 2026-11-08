import { expect, test } from '@playwright/test';
import { load } from './helpers';

test.beforeEach(async ({ page }) => load(page, 'light'));

test('skip link is the first tab stop and moves focus to the content', async ({ page }) => {
	await page.keyboard.press('Tab');
	const skip = page.getByRole('link', { name: 'Skip to content' });
	await expect(skip).toBeFocused();
	await expect(skip).toBeInViewport();
	await page.keyboard.press('Enter');
	await expect(page.locator('#content')).toBeFocused();
});

test('Ctrl/Cmd+K opens the command palette; Escape closes it and restores focus', async ({
	page,
	browserName
}) => {
	test.skip(browserName !== 'chromium');
	const search = page.getByRole('button', { name: /search and commands/i });
	await search.focus();
	await page.keyboard.press('ControlOrMeta+k');
	const dialog = page.getByRole('dialog', { name: 'Command menu' });
	await expect(dialog).toBeVisible();
	await expect(page.getByRole('combobox', { name: /search games, sections/i })).toBeFocused();
	await page.keyboard.press('Escape');
	await expect(dialog).toBeHidden();
	await expect(search).toBeFocused();
});

test('/ also opens the palette, and arrow keys + Enter run a command', async ({ page }) => {
	await page.keyboard.press('/');
	await page.keyboard.type('trait explorer');
	await expect(page.getByRole('option', { name: /Trait explorer/ }).first()).toHaveAttribute(
		'aria-selected',
		'true'
	);
	await page.keyboard.press('Enter');
	await expect(page.getByRole('dialog', { name: 'Command menu' })).toBeHidden();
	await expect(page.locator('#traits')).toBeInViewport();
});

test('picking a game opens its drawer; Tab stays inside; Escape returns focus', async ({
	page
}) => {
	const search = page.getByRole('button', { name: /search and commands/i });
	await search.click();
	await page.keyboard.type('Gloomhaven');
	await page.keyboard.press('Enter');
	const drawer = page.getByRole('dialog', { name: /Gloomhaven/ });
	await expect(drawer).toBeVisible();
	for (let i = 0; i < 25; i++) {
		await page.keyboard.press('Tab');
		const inside = await drawer.evaluate((d) => d.contains(document.activeElement));
		expect(inside).toBe(true);
	}
	await page.keyboard.press('Escape');
	await expect(drawer).toBeHidden();
	await expect(search).toBeFocused();
});

test('every focusable control shows a visible focus indicator', async ({ page }) => {
	const missing = await page.evaluate(() => {
		const els = [
			...document.querySelectorAll<HTMLElement>(
				'a[href], button:not([tabindex="-1"]):not(:disabled), input, select, [tabindex="0"], summary'
			)
		].filter((e) => e.getClientRects().length);
		const bad: string[] = [];
		// SVG marks can't draw an outline, so for them a focus ring means some child gains a stroke.
		const strokes = (e: Element) =>
			[...e.querySelectorAll('*')].map((c) => {
				const cs = getComputedStyle(c);
				return `${cs.stroke}/${cs.strokeWidth}`;
			});
		for (const e of els) {
			const before = e instanceof SVGElement ? strokes(e) : [];
			e.focus({ focusVisible: true } as FocusOptions);
			const cs = getComputedStyle(e);
			const ring = cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2;
			const svgRing =
				e instanceof SVGElement &&
				strokes(e).some((s, i) => s !== before[i] && !s.startsWith('none'));
			if (!ring && cs.boxShadow === 'none' && !svgRing) bad.push(e.outerHTML.slice(0, 80));
		}
		(document.activeElement as HTMLElement | null)?.blur();
		return bad;
	});
	expect(missing).toEqual([]);
});
