<script lang="ts">
	import type { Snippet } from 'svelte';

	let { x, y, width, children }: { x: number; y: number; width: number; children: Snippet } =
		$props();

	// Flip to the left of the pointer near the right edge so the tooltip never clips.
	const flip = $derived(x > width * 0.62);
</script>

<div class="tooltip" style:left="{x}px" style:top="{y}px" class:flip role="status">
	{@render children()}
</div>

<style>
	.tooltip {
		position: absolute;
		pointer-events: none;
		transform: translate(14px, -50%);
		background: var(--surface-1);
		border: 1px solid var(--border);
		box-shadow: var(--shadow);
		border-radius: 8px;
		padding: 0.5rem 0.65rem;
		font-size: 0.8rem;
		line-height: 1.35;
		color: var(--text-secondary);
		min-width: 140px;
		max-width: 260px;
		z-index: 5;
		white-space: normal;
	}
	.flip {
		transform: translate(calc(-100% - 14px), -50%);
	}
	.tooltip :global(.v) {
		color: var(--text-primary);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.tooltip :global(.t) {
		color: var(--text-primary);
		font-weight: 600;
		display: block;
		margin-bottom: 0.15rem;
	}
	.tooltip :global(.row) {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
	}
</style>
