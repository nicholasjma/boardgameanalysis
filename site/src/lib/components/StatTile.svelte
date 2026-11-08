<script lang="ts">
	import { Tween, prefersReducedMotion } from 'svelte/motion';
	import { cubicOut } from 'svelte/easing';
	import { inview } from '#lib/inview.ts';

	let {
		label,
		value,
		format = (n: number) => n.toLocaleString('en-US'),
		note = ''
	}: { label: string; value: number; format?: (n: number) => string; note?: string } = $props();

	// Start at the real value so prerendered HTML (and no-JS readers) see it; count up on reveal.
	// svelte-ignore state_referenced_locally
	const shown = new Tween(value, { duration: 1100, easing: cubicOut });
	function start() {
		if (prefersReducedMotion.current) return;
		shown.set(0, { duration: 0 });
		shown.set(value);
	}
</script>

<div class="tile" use:inview={start}>
	<div class="label">{label}</div>
	<div class="value" aria-label={format(value)}>{format(shown.current)}</div>
	{#if note}<div class="note">{note}</div>{/if}
</div>

<style>
	.tile {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: var(--radius);
		padding: 0.9rem 1rem;
	}
	.label {
		font-size: 0.8rem;
		color: var(--text-secondary);
	}
	.value {
		font-size: 1.9rem;
		font-weight: 650;
		letter-spacing: -0.02em;
		color: var(--text-primary);
		line-height: 1.2;
	}
	.note {
		font-size: 0.78rem;
		color: var(--text-muted);
	}
</style>
