import { getToken } from './token';

export type WsEvent = { type: string; payload: unknown };

export function connectWs(onEvent: (e: WsEvent) => void): () => void {
	const proto = location.protocol === 'https:' ? 'wss' : 'ws';
	const ws = new WebSocket(`${proto}://${location.host}/ws`);
	ws.onopen = () => {
		const t = getToken();
		if (t) ws.send(t);
	};
	ws.onmessage = (m) => {
		try {
			onEvent(JSON.parse(m.data));
		} catch {
			/* ignore malformed frames */
		}
	};
	return () => ws.close();
}
