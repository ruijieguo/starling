import { getToken } from './token';

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
	const headers = new Headers(init.headers);
	const tok = getToken();
	if (tok) headers.set('Authorization', `Bearer ${tok}`);
	headers.set('Content-Type', 'application/json');
	const res = await fetch(path, { ...init, headers });
	if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
	return res.json() as Promise<T>;
}

export const api = {
	get: <T>(p: string) => req<T>(p),
	post: <T>(p: string, body: unknown) =>
		req<T>(p, { method: 'POST', body: JSON.stringify(body) })
};
