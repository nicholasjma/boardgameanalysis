/**
 * Geometry for the 3D map: the UMAP points framed in a unit box, each game's nearest neighbours,
 * similarity lists, and named regions for the zoomed-out view.
 */
import { scaleSqrt } from 'd3';
import { data, type Game } from '#lib/data.ts';

export type Vec = [number, number, number];
export type Pt = { g: Game; p: Vec; near: number[]; region: number };

export const pts: Pt[] = data.games
	.filter((g) => g.umap)
	.map((g) => ({ g, p: [...(g.umap as Vec)], near: [], region: -1 }));

// Fit the bulk of the cloud (2nd–98th percentile on each axis) inside the unit sphere, so a
// few outliers don't shrink everything else. Outliers simply sit a little outside the frame.
const quantile = (k: number, f: number) => {
	const v = pts.map((d) => d.p[k]).sort((a, b) => a - b);
	return v[Math.round(f * (v.length - 1))];
};
const lo = [0, 1, 2].map((k) => quantile(k, 0.02));
const hi = [0, 1, 2].map((k) => quantile(k, 0.98));
const half = [0, 1, 2].map((k) => (hi[k] - lo[k]) / 2);
const diag = Math.hypot(...half) || 1;
for (const d of pts) d.p = d.p.map((v, k) => (v - (lo[k] + hi[k]) / 2) / diag) as Vec;
export const box = half.map((h) => h / diag) as Vec;

export const dist2 = (a: Vec, b: Vec) =>
	(a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;

// Nearest neighbours in the embedding (brute force: 1,000² distances is cheap).
const K = 5;
for (const a of pts) {
	const best: [number, number][] = [];
	pts.forEach((b, j) => {
		if (a === b) return;
		const d = dist2(a.p, b.p);
		if (best.length < K || d < best[K - 1][0]) {
			best.push([d, j]);
			best.sort((x, y) => x[0] - y[0]);
			if (best.length > K) best.pop();
		}
	});
	a.near = best.map(([, j]) => j);
}

export const indexById = new Map(pts.map((p, i) => [p.g.id, i]));
export const dotSize = scaleSqrt()
	.domain([0, Math.max(...pts.map((p) => p.g.votes))])
	.range([2, 7.5]);
export const traitIndex = new Map(data.traitKeys.map((k, i) => [k, i]));

/** Shared trait indices of two games (both lists are sorted ascending). */
export function shared(a: number[], b: number[]): number[] {
	const out: number[] = [];
	for (let i = 0, j = 0; i < a.length && j < b.length;) {
		if (a[i] === b[j]) {
			out.push(a[i]);
			i++;
			j++;
		} else if (a[i] < b[j]) i++;
		else j++;
	}
	return out;
}

export type Similar = { i: number; sim: number; common: number[] };
export const N_SIMILAR = 10;

/**
 * The games most like pts[i], by Jaccard similarity of their categories and mechanics (the
 * same distance the embedding was built from), ties broken by distance on the map.
 */
export function similarTo(i: number): Similar[] {
	const a = pts[i];
	return pts
		.map((b, j) => {
			const common = shared(a.g.traits, b.g.traits);
			const union = a.g.traits.length + b.g.traits.length - common.length;
			return { i: j, sim: union ? common.length / union : 0, common, d: dist2(a.p, b.p) };
		})
		.filter((x) => x.i !== i)
		.sort((x, y) => y.sim - x.sim || x.d - y.d)
		.slice(0, N_SIMILAR)
		.map(({ i, sim, common }) => ({ i, sim, common }));
}

const mean = (list: Vec[]): Vec =>
	[0, 1, 2].map((k) => list.reduce((s, p) => s + p[k], 0) / (list.length || 1)) as Vec;

/** The middle of the games that have a trait: where the tour flies to show it. */
export function traitCentre(key: string): Vec {
	const bit = traitIndex.get(key) ?? -1;
	return mean(pts.filter((d) => d.g.traits.includes(bit)).map((d) => d.p));
}

// --- Regions: k-means on the 3D coordinates, named by their most over-represented traits ------
export type Region = { id: number; name: string; traits: string[]; c: Vec; n: number };

function kmeans(k: number, seed = 7): number[] {
	let s = seed;
	const rand = () => {
		// mulberry32: deterministic, so the regions are the same on every visit
		s = (s + 0x6d2b79f5) | 0;
		let t = Math.imul(s ^ (s >>> 15), 1 | s);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
	const P = pts.map((d) => d.p);
	// k-means++ seeding
	const cent: Vec[] = [[...P[Math.floor(rand() * P.length)]] as Vec];
	while (cent.length < k) {
		const w = P.map((p) => Math.min(...cent.map((c) => dist2(p, c))));
		let r = rand() * w.reduce((a, b) => a + b, 0);
		const i = Math.max(
			0,
			w.findIndex((x) => (r -= x) <= 0)
		);
		cent.push([...P[i]] as Vec);
	}
	let lab = P.map(() => 0);
	for (let it = 0; it < 25; it++) {
		lab = P.map((p) => {
			let best = 0;
			for (let c = 1; c < k; c++) if (dist2(p, cent[c]) < dist2(p, cent[best])) best = c;
			return best;
		});
		for (let c = 0; c < k; c++) {
			const m = P.filter((_, i) => lab[i] === c);
			if (m.length) cent[c] = mean(m);
		}
	}
	return lab;
}

export const regions: Region[] = (() => {
	const lab = kmeans(12);
	const N = pts.length;
	const overall = new Map<number, number>();
	for (const d of pts) for (const t of d.g.traits) overall.set(t, (overall.get(t) ?? 0) + 1);
	const out: Region[] = [];
	for (let c = 0; c < 12; c++) {
		const members = pts.filter((_, i) => lab[i] === c);
		if (members.length < 20) continue; // a handful of outliers is not a region
		const n = members.length;
		const count = new Map<number, number>();
		for (const d of members) for (const t of d.g.traits) count.set(t, (count.get(t) ?? 0) + 1);
		const named = [...count]
			.map(([t, m]) => {
				const share = m / n;
				const lift = share / ((overall.get(t) ?? 1) / N);
				return { t, score: share >= 0.3 && lift > 1.3 ? share * Math.log(lift) : 0 };
			})
			.filter((x) => x.score > 0)
			.sort((a, b) => b.score - a.score)
			.slice(0, 2)
			.map((x) => data.traits[x.t]?.name ?? '');
		if (!named.length) continue;
		const id = out.length;
		for (let i = 0; i < N; i++) if (lab[i] === c) pts[i].region = id;
		out.push({ id, name: named.join(' · '), traits: named, c: mean(members.map((d) => d.p)), n });
	}
	return out
		.sort((a, b) => b.n - a.n)
		.map((r, id) => {
			for (const d of pts) if (d.region === r.id) d.region = -100 - id; // re-key after sorting
			return { ...r, id };
		});
})();
for (const d of pts)
	if (d.region <= -100) d.region = -100 - d.region;
	else d.region = -1;
