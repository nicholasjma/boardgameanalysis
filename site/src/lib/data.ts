import raw from './data/analysis.json';

export type Kind = 'numeric' | 'category' | 'mechanic';

export interface Game {
	id: number;
	name: string;
	rank: number;
	year: number;
	rating: number;
	geek: number | null;
	pred: number;
	magic: number;
	votes: number;
	weight: number | null;
	time: number;
	players: [number, number];
	traits: number[];
	dist?: number[];
	wish?: number;
	then?: { rank: number; rating: number };
	cluster?: number;
	tsne?: [number, number];
	umap?: [number, number, number];
	why?: { base: number; parts: [string, number][]; other: number };
}

export interface Trait {
	key: string;
	name: string;
	kind: Kind;
	count: number;
	meanRating: number;
	meanMagic: number;
	meanWeight: number | null;
	effect: number | null;
	importance: number;
	ratings: number[];
}

export interface Bin {
	x0: number;
	x1: number;
	n: number;
}

export interface Cluster {
	id: number;
	name: string;
	size: number;
	meanRating: number;
	meanMagic: number;
	topGames: number[];
	traits: { name: string; share: number }[];
}

export interface Shift {
	name: string;
	kind: Kind;
	then: number;
	now: number;
}

export interface Analysis {
	meta: {
		version: string;
		generated: string;
		source: string;
		snapshot: string;
		games: number;
		features: number;
		categories: number;
		mechanics: number;
		rmse: number;
		foldRmse: number[];
		baselineStd: number;
		r2: number;
		meanRating: number;
		baseYear: number;
		minVotes: number;
	};
	traitKeys: string[];
	traits: Trait[];
	games: Game[];
	importance: { feature: string; kind: Kind; meanAbs: number }[];
	beeswarm: { feature: string; kind: Kind; meanAbs: number; points: [number, number][] }[];
	dependence: Record<'years_since_base' | 'avg_time', [number, number][]>;
	residuals: Bin[];
	ratingHistogram: Bin[];
	clusters: Cluster[];
	years: { year: number; n: number; rating: number; pred: number; weight: number | null }[];
	compare: {
		snapshot: string;
		top: number;
		retained: number;
		newSince: number;
		stats: Record<
			'medianYear' | 'meanWeight' | 'meanTime' | 'meanRating' | 'medianVotes',
			[number, number]
		>;
		shifts: Shift[];
	} | null;
}

export const data = raw as unknown as Analysis;
export const gamesById = new Map(data.games.map((g) => [g.id, g]));

export const fmt = {
	int: new Intl.NumberFormat('en-US').format,
	compact: new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format,
	r2: (n: number) => n.toFixed(2),
	r3: (n: number) => n.toFixed(3),
	signed: (n: number, d = 2) => `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(d)}`,
	pct: (n: number, d = 0) => `${(n * 100).toFixed(d)}%`
};

export const bggUrl = (id: number) => `https://boardgamegeek.com/boardgame/${id}`;

export const kindLabel: Record<Kind, string> = {
	numeric: 'Numeric',
	category: 'Category',
	mechanic: 'Mechanic'
};

/** Shorten a label to fit `px` of 12–13px text, keeping the full text for a <title>. */
export function fit(label: string, px: number, charPx = 6.6): string {
	const max = Math.max(6, Math.floor(px / charPx));
	return label.length <= max ? label : `${label.slice(0, max - 1).trimEnd()}…`;
}
