<script lang="ts">
	import { eras } from '#lib/era.ts';
	let { title = 'Year published' }: { title?: string } = $props();
</script>

<ul class="legend" aria-label={title}>
	<li class="ttl">{title}</li>
	{#each eras as era, i (era.label)}
		<li><span class="swatch dot" style:background="var(--ord-{i + 1})"></span>{era.label}</li>
	{/each}
</ul>

<style>
	.ttl {
		color: var(--text-muted);
	}
</style>
