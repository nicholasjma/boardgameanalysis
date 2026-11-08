import { defineConfig, devices } from '@playwright/test';

// Accessibility and contrast tests run against the production build (`npm run build` first).
export default defineConfig({
	testDir: 'tests',
	fullyParallel: true,
	forbidOnly: !!process.env.CI,
	// No retries: a test that only passes on a second try is a failure we want to see.
	retries: 0,
	reporter: process.env.CI ? [['github'], ['list']] : 'list',
	use: { baseURL: 'http://localhost:4173', trace: 'retain-on-failure' },
	projects: [
		{
			name: 'desktop',
			use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } }
		},
		{ name: 'mobile', use: { ...devices['Pixel 7'] } }
	],
	webServer: {
		command: 'npm run preview -- --port 4173 --strictPort',
		port: 4173,
		reuseExistingServer: !process.env.CI
	}
});
