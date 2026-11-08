import { Delaunay } from 'd3';

export interface Pt<T> {
	x: number;
	y: number;
	d: T;
}

/** Nearest-point lookup (Voronoi) so the pointer only has to be closest, not on the dot. */
export function nearest<T>(points: Pt<T>[], maxDist = 28) {
	const delaunay = Delaunay.from(
		points,
		(p) => p.x,
		(p) => p.y
	);
	return (e: PointerEvent): Pt<T> | null => {
		const rect = (e.currentTarget as Element).getBoundingClientRect();
		const px = e.clientX - rect.left;
		const py = e.clientY - rect.top;
		if (!points.length) return null;
		const p = points[delaunay.find(px, py)];
		return p && Math.hypot(p.x - px, p.y - py) <= maxDist ? p : null;
	};
}
