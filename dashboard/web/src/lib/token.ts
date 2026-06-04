const KEY = 'starling_dash_token';
export const getToken = (): string =>
	(typeof localStorage !== 'undefined' && localStorage.getItem(KEY)) || '';
export const setToken = (t: string): void => {
	if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, t);
};
