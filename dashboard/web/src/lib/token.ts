const KEY = 'starling_dash_token';

export const getToken = (): string =>
	(typeof localStorage !== 'undefined' && localStorage.getItem(KEY)) || '';

export const setToken = (t: string): void => {
	if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, t);
};

/** Read a `#token=…` URL fragment into storage, then strip it from the address bar.
 *  Fragments are never sent to the server, so the token never lands in access logs. */
export function adoptTokenFromHash(): void {
	if (typeof location === 'undefined' || !location.hash) return;
	const m = location.hash.match(/(?:^#|&)token=([^&]+)/);
	if (m) {
		setToken(decodeURIComponent(m[1]));
		const cleaned = location.hash.replace(/(?:^#|&)token=[^&]+/, '').replace(/^#&?/, '#');
		history.replaceState(null, '', location.pathname + location.search + (cleaned === '#' ? '' : cleaned));
	}
}
