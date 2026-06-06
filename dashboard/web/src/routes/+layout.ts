import { adoptTokenFromHash } from '$lib/token';

export const ssr = false;
export const prerender = false;

// Adopt a `#token=…` login fragment here, before the layout/page components
// render and before any page `$effect` fires its first /api request. With
// ssr=false this load runs client-side, so the very first data fetch already
// carries the bearer token (fixes the first-load 401 race on the landing page).
export function load() {
	adoptTokenFromHash();
}
