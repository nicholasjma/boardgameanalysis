/** Publication-era buckets mapped to an ordinal one-hue ramp (CSS vars --ord-1..5). */
export const eras = [
	{ label: 'Before 2005', max: 2004 },
	{ label: '2005–2012', max: 2012 },
	{ label: '2013–2017', max: 2017 },
	{ label: '2018–2021', max: 2021 },
	{ label: '2022+', max: Infinity }
] as const;

export function eraIndex(year: number): number {
	return eras.findIndex((e) => year <= e.max);
}

export const eraColor = (year: number) => `var(--ord-${eraIndex(year) + 1})`;

/** Average-rating bands on the same ramp, used by the family map and the 3D map. */
export const ratingBands = [
	{ label: 'Under 7.6', max: 7.6 },
	{ label: '7.6–7.9', max: 7.9 },
	{ label: '7.9–8.2', max: 8.2 },
	{ label: '8.2–8.5', max: 8.5 },
	{ label: '8.5+', max: Infinity }
] as const;

/** 1-based band index, matching the --ord-N custom properties. */
export const ratingBand = (r: number) => ratingBands.findIndex((b) => r < b.max) + 1;
