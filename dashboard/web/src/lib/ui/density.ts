import { writable } from 'svelte/store';

export type Density = 'comfortable' | 'compact';
const KEY = 'starling_density';

/** Rows-per-page default per density (used by DataTable). */
export const pageSizeFor = (d: Density): number => (d === 'compact' ? 25 : 12);

const initial: Density =
	(typeof localStorage !== 'undefined' && (localStorage.getItem(KEY) as Density | null)) ||
	'comfortable';

export const density = writable<Density>(initial);

/** Write the density to <html data-density> + persist the chosen mode. */
export function applyDensity(d: Density): void {
	if (typeof document !== 'undefined') document.documentElement.dataset.density = d;
	if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, d);
}

/** comfortable → compact → comfortable. */
export const cycleDensity = (d: Density): Density => (d === 'comfortable' ? 'compact' : 'comfortable');
