import js from '@eslint/js';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

export default ts.config(
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	{ languageOptions: { globals: { ...globals.browser, ...globals.node } } },
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: { parserOptions: { parser: ts.parser, extraFileExtensions: ['.svelte'] } }
	},
	{
		rules: {
			// External links only; there is a single page, so nothing to resolve().
			'svelte/no-navigation-without-resolve': ['error', { ignoreLinks: true }]
		}
	},
	{ ignores: ['build/', '.svelte-kit/', 'node_modules/'] }
);
