<script lang="ts">
	import { data, fmt, type Game } from '#lib/data.ts';
	import { flyTo, openGame } from '#lib/state.svelte.ts';

	type Key = 'rank' | 'name' | 'year' | 'rating' | 'pred' | 'magic' | 'votes' | 'weight';
	type Col = { key: Key; label: string; num?: boolean; fmt?: (v: number) => string };
	const cols: Col[] = [
		{ key: 'rank', label: 'Rank', num: true },
		{ key: 'name', label: 'Game' },
		{ key: 'year', label: 'Year', num: true },
		{ key: 'rating', label: 'Rating', num: true, fmt: fmt.r2 },
		{ key: 'pred', label: 'Predicted', num: true, fmt: fmt.r2 },
		{ key: 'magic', label: 'Magic', num: true, fmt: (v) => fmt.signed(v) },
		{ key: 'votes', label: 'Ratings', num: true, fmt: fmt.int },
		{ key: 'weight', label: 'Weight', num: true, fmt: fmt.r2 }
	];

	let sortKey = $state<Key>('rank');
	let asc = $state(true);
	let q = $state('');
	let page = $state(0);
	const per = 25;

	const rows = $derived.by(() => {
		const s = q.trim().toLowerCase();
		const filtered = s ? data.games.filter((g) => g.name.toLowerCase().includes(s)) : data.games;
		return [...filtered].sort((a: Game, b: Game) => {
			const av = a[sortKey] ?? -Infinity;
			const bv = b[sortKey] ?? -Infinity;
			const c = av < bv ? -1 : av > bv ? 1 : 0;
			return asc ? c : -c;
		});
	});
	const pages = $derived(Math.max(1, Math.ceil(rows.length / per)));
	const view = $derived(rows.slice(page * per, page * per + per));

	function sortBy(k: Key) {
		if (sortKey === k) asc = !asc;
		else {
			sortKey = k;
			asc = k === 'rank' || k === 'name';
		}
		page = 0;
	}
</script>

<div class="tbl">
	<div class="bar">
		<input
			type="search"
			placeholder="Filter by name…"
			bind:value={q}
			oninput={() => (page = 0)}
			aria-label="Filter games by name"
		/>
		<span class="count">{fmt.int(rows.length)} games</span>
	</div>
	<div class="scroll">
		<table>
			<thead>
				<tr>
					{#each cols as c (c.key)}
						<th
							class:num={c.num}
							aria-sort={sortKey === c.key ? (asc ? 'ascending' : 'descending') : 'none'}
						>
							<button onclick={() => sortBy(c.key)}>
								{c.label}{sortKey === c.key ? (asc ? ' ↑' : ' ↓') : ''}
							</button>
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each view as g (g.id)}
					<tr>
						{#each cols as c (c.key)}
							{@const v = g[c.key]}
							<td class:num={c.num}>
								{#if c.key === 'name'}
									<span class="name">
										<button class="link" onclick={() => openGame(g.id)}>{g.name}</button>
										{#if g.umap}
											<button class="fly" onclick={() => flyTo(g.id)}
												><span class="visually-hidden">Show {g.name} on the </span>3D map</button
											>
										{/if}
									</span>
								{:else if v === null || v === undefined}
									—
								{:else if c.fmt}
									{c.fmt(v as number)}
								{:else}
									{v}
								{/if}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<div class="pager">
		<button class="chip" disabled={page === 0} onclick={() => (page -= 1)}>← Prev</button>
		<span>Page {page + 1} of {pages}</span>
		<button class="chip" disabled={page >= pages - 1} onclick={() => (page += 1)}>Next →</button>
	</div>
</div>

<style>
	.bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.6rem;
	}
	input {
		background: var(--surface-1);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.4rem 0.7rem;
		width: min(320px, 60vw);
	}
	.count {
		color: var(--text-muted);
		font-size: 0.85rem;
	}
	.scroll {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.86rem;
		font-variant-numeric: tabular-nums;
	}
	th,
	td {
		padding: 0.45rem 0.6rem;
		border-bottom: 1px solid var(--grid);
		text-align: left;
		white-space: nowrap;
	}
	th button {
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
		font-weight: 600;
		color: var(--text-secondary);
	}
	.num {
		text-align: right;
	}
	.link {
		background: none;
		border: 0;
		padding: 0;
		color: var(--text-primary);
		cursor: pointer;
		text-align: left;
		white-space: normal;
	}
	.name {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}
	.fly {
		flex: none;
		border: 1px solid var(--border);
		background: var(--surface-1);
		color: var(--text-secondary);
		border-radius: 999px;
		padding: 0.05rem 0.5rem;
		font-size: 0.72rem;
		font-weight: 600;
		cursor: pointer;
		min-height: 24px;
	}
	.fly:hover {
		color: var(--text-primary);
		border-color: var(--series-1);
	}
	.link:hover {
		text-decoration: underline;
	}
	.pager {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		justify-content: flex-end;
		margin-top: 0.75rem;
		font-size: 0.85rem;
		color: var(--text-muted);
	}
	.chip:disabled {
		opacity: 0.4;
		cursor: default;
	}
</style>
