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
	await expect(page.getByRole('combobox', { name: /search games, chapters/i })).toBeFocused();
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
	await expect(page.getByRole('heading', { name: 'Pick a mechanic or category' })).toBeFocused();
	await expect(page).toHaveURL(/#traits$/);
});

test('picking a game opens its drawer; Tab stays inside; Escape returns focus', async ({
	page
}) => {
	const search = page.getByRole('button', { name: /search and commands/i });
	await search.click();
	await page.keyboard.type('Gloomhaven');
	await page.keyboard.press('Shift+Enter');
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

test('3D map: search flies to a game and lists similar games', async ({ page }) => {
	const search = page.getByRole('combobox', { name: 'Fly to a game' });
	await search.fill('Gloomhaven');
	await expect(page.getByRole('option', { name: /^Gloomhaven #/ })).toHaveAttribute(
		'aria-selected',
		'true'
	);
	await search.press('Enter');
	const panel = page.getByRole('complementary', { name: 'Map panel' });
	await expect(panel.locator('.sel-name')).toHaveText('Gloomhaven');
	const similar = panel.getByRole('list').getByRole('button');
	await expect(similar).toHaveCount(10);
	await expect(page.getByRole('status').filter({ hasText: 'most similar' })).toHaveText(
		/Gloomhaven and its 10 most similar games/
	);

	// Hopping to a neighbour re-centres the panel on it.
	const next = (await similar.first().locator('.sim-name').textContent())!;
	await similar.first().click();
	await expect(panel.locator('.sel-name')).toHaveText(next);
	await panel.getByRole('button', { name: 'Clear' }).click();
	await expect(panel.locator('.sel-name')).toHaveCount(0);
});

test('the game drawer links to the game on the 3D map', async ({ page }) => {
	await page.getByRole('button', { name: /search and commands/i }).click();
	await page.keyboard.type('Wingspan');
	await page.keyboard.press('Shift+Enter');
	await page.getByRole('button', { name: 'Show similar games on the 3D map' }).click();
	await expect(page.locator('#space .sel-name')).toHaveText('Wingspan');
	await expect(page.locator('#space .sel-name')).toBeFocused();
});

test('palette: Enter on a game flies to it on the 3D map', async ({ page }) => {
	await page.getByRole('button', { name: /search and commands/i }).click();
	await page.keyboard.type('Terraforming Mars');
	await page.keyboard.press('Enter');
	await expect(page.getByRole('dialog', { name: 'Command menu' })).toBeHidden();
	await expect(page.locator('#space .sel-name')).toHaveText('Terraforming Mars');
	await expect(page.locator('#space .sel-name')).toBeFocused();
});

test('palette: the Details pill on a game result opens its drawer', async ({ page, isMobile }) => {
	test.skip(isMobile, 'hover-revealed pill; touch shows it always but Playwright taps differ');
	await page.getByRole('button', { name: /search and commands/i }).click();
	await page.keyboard.type('Ark Nova');
	const row = page.getByRole('option', { name: /^Ark Nova/ });
	await row.hover();
	await row.locator('.map').click();
	await expect(page.getByRole('dialog', { name: /Ark Nova/ })).toBeVisible();
});

test('chapters open over the map; a game in the rankings flies there and back', async ({
	page
}) => {
	const toc = page.getByRole('link', { name: /All games/ }).last();
	await toc.click();
	const heading = page.getByRole('heading', { name: 'Every game, every number' });
	await expect(heading).toBeFocused();
	await expect(page).toHaveURL(/#games$/);

	const fly = page.getByRole('button', { name: 'Show Ark Nova on the 3D map' });
	await page.getByRole('searchbox', { name: 'Filter games by name' }).fill('Ark Nova');
	await fly.click();
	await expect(heading).toBeHidden();
	await expect(page.locator('#space .sel-name')).toHaveText('Ark Nova');

	await page.getByRole('button', { name: 'Back to All games' }).click();
	await expect(heading).toBeVisible();
	await expect(fly).toBeFocused();

	// Escape closes the chapter. The link that opened it has made way for Ark Nova in the map
	// panel, so focus lands on Ark Nova.
	await page.keyboard.press('Escape');
	await expect(heading).toBeHidden();
	await expect(page.locator('#space .sel-name')).toBeFocused();
	await expect(page).not.toHaveURL(/#games$/);
});

test('chapter links work from the URL and the back button closes them', async ({ page }) => {
	await page.goto('/#magic');
	await expect(page.getByRole('heading', { name: 'What the traits can’t explain' })).toBeVisible();
	await page
		.getByRole('link', { name: /Next: Trait explorer/ })
		.first()
		.click();
	await expect(page.getByRole('heading', { name: 'Pick a mechanic or category' })).toBeFocused();
	await page.goBack();
	await expect(page.getByRole('heading', { name: 'What the traits can’t explain' })).toBeVisible();
});

test('W A S D fly the camera', async ({ page }) => {
	const canvas = page.locator('#space canvas');
	await canvas.focus();
	const shot = () =>
		canvas.evaluate((c: HTMLCanvasElement) => {
			const d = c.getContext('2d')!.getImageData(0, 0, c.width, c.height).data;
			let h = 0;
			for (let i = 0; i < d.length; i += 101) h = (h * 31 + d[i]) | 0;
			return h;
		});
	const before = await shot();
	await page.keyboard.down('w');
	await page.waitForTimeout(400);
	await page.keyboard.up('w');
	await page.waitForTimeout(200);
	expect(await shot()).not.toBe(before);
});

test('the tour: scrolling its story recolours the map (semantic scroll)', async ({ page }) => {
	await page.getByRole('button', { name: 'Take the tour' }).click();
	await expect(page.getByRole('heading', { name: 'Guided tour' })).toBeFocused();
	const year = page.getByRole('button', { name: 'Year', exact: true });
	await expect(year).toHaveAttribute('aria-pressed', 'false');
	await page.getByRole('heading', { name: 'Newer games rate higher' }).scrollIntoViewIfNeeded();
	await page
		.locator('.tour')
		.evaluate((t) =>
			t.querySelector('[data-i="3"]')!.scrollIntoView({ block: 'start', behavior: 'instant' })
		);
	await expect(year).toHaveAttribute('aria-pressed', 'true');

	await page.getByRole('button', { name: 'Exit tour' }).click();
	await expect(page.getByRole('button', { name: 'Rating', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
});

test('the top 100 can be walked on the map', async ({ page }) => {
	const panel = page.getByRole('complementary', { name: 'Map panel' });
	await panel.getByRole('list', { name: 'Top 100' }).getByRole('button').first().click();
	const name = panel.locator('.sel-name');
	const first = (await name.textContent())!;
	await expect(panel.locator('.sel-meta')).toHaveText(/^#1 /);
	await panel.getByRole('button', { name: /next in the ranking/ }).click();
	await expect(panel.locator('.sel-meta')).toHaveText(/^#2 /);
	await page.locator('#space canvas').focus();
	await page.keyboard.press('[');
	await expect(name).toHaveText(first);
});

test('every game family opens without errors (trait names can repeat)', async ({ page }) => {
	// Regression: "Deduction" is both a category and a mechanic, and a list keyed by name threw.
	const errors: string[] = [];
	page.on('pageerror', (e) => errors.push(e.message));
	await page.goto('/#map');
	const families = page.getByRole('listbox', { name: 'Game families' }).getByRole('option');
	await expect(families.first()).toBeVisible();
	for (let i = 0; i < (await families.count()); i++) {
		await families.nth(i).click();
		await expect(page.getByText(/^What defines/)).toBeVisible();
	}
	// The family with both Deductions labels which is which.
	const deduction = families.filter({ hasText: /Deduction/ }).first();
	if ((await deduction.getAttribute('aria-selected')) !== 'true') await deduction.click();
	await expect(page.getByText('(mechanic)').first()).toBeVisible();
	expect(errors).toEqual([]);
});
