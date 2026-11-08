<script lang="ts">
	import { onMount } from 'svelte';
	import { initTheme, toggleTheme, ui } from '#lib/state.svelte.ts';

	onMount(initTheme);
</script>

<button
	class="toggle"
	onclick={toggleTheme}
	aria-label="Dark theme"
	aria-pressed={ui.theme === 'dark'}
	title="Toggle dark theme"
>
	{#if ui.theme === 'dark'}
		<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
			<circle cx="12" cy="12" r="4.5" />
			<path
				d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
				stroke-width="2"
				stroke-linecap="round"
			/>
		</svg>
	{:else}
		<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
			<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
		</svg>
	{/if}
</button>

<style>
	.toggle {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 999px;
		width: 36px;
		height: 36px;
		display: grid;
		place-items: center;
		cursor: pointer;
		flex: none;
	}
	svg {
		fill: var(--text-secondary);
		stroke: var(--text-secondary);
	}
</style>
