export type Density = 'comfortable' | 'compact';

/** Rows-per-page default per density (used by DataTable). */
export const pageSizeFor = (d: Density): number => (d === 'compact' ? 25 : 12);
