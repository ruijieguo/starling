import { writable } from 'svelte/store';

export type Theme = 'light' | 'dark' | 'system';
const KEY = 'starling_theme';

const systemDark = (): boolean =>
	typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches;

/** Resolve 'system' to a concrete light/dark using the OS preference. */
export const resolveTheme = (t: Theme): 'light' | 'dark' =>
	t === 'system' ? (systemDark() ? 'dark' : 'light') : t;

const initial: Theme =
	(typeof localStorage !== 'undefined' && (localStorage.getItem(KEY) as Theme | null)) || 'system';

export const theme = writable<Theme>(initial);

/** Write the resolved theme to <html data-theme> + persist the chosen mode. */
export function applyTheme(t: Theme): void {
	if (typeof document !== 'undefined') document.documentElement.dataset.theme = resolveTheme(t);
	if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, t);
}

/** light → dark → system → light. */
export const cycleTheme = (t: Theme): Theme =>
	t === 'light' ? 'dark' : t === 'dark' ? 'system' : 'light';
