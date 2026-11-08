/** Cross-chart selection: the open game and the trait under the explorer. */
export const ui = $state({
	game: null as number | null,
	trait: 'mech:Cooperative Game' as string,
	hoverGame: null as number | null
});

export function openGame(id: number) {
	ui.game = id;
}

export function closeGame() {
	ui.game = null;
}
