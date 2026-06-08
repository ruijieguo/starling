import { getToken } from './token';
import { wsConn } from './health';

export type WsEvent = { type: string; payload: unknown };

const PING_MS = 25000;
const MAX_BACKOFF_MS = 10000;

/**
 * 连接 /ws,自动重连(指数退避到 10s 封顶)+ 心跳。连接态写入 wsConn store。
 * 返回一个 dispose 函数:调用后停止重连并关闭。
 */
export function connectWs(onEvent: (e: WsEvent) => void): () => void {
	let ws: WebSocket | null = null;
	let pingTimer: ReturnType<typeof setInterval> | null = null;
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let attempt = 0;
	let disposed = false;

	function open() {
		if (disposed) return;
		wsConn.set('connecting');
		const proto = location.protocol === 'https:' ? 'wss' : 'ws';
		ws = new WebSocket(`${proto}://${location.host}/ws`);
		ws.onopen = () => {
			attempt = 0;
			wsConn.set('open');
			const t = getToken();
			if (t) ws?.send(t);
			pingTimer = setInterval(() => {
				if (ws?.readyState === WebSocket.OPEN) ws.send('ping');
			}, PING_MS);
		};
		ws.onmessage = (m) => {
			if (m.data === 'pong') return;
			try {
				onEvent(JSON.parse(m.data));
			} catch {
				/* 忽略畸形帧 */
			}
		};
		ws.onerror = () => ws?.close();
		ws.onclose = () => {
			if (pingTimer) clearInterval(pingTimer);
			wsConn.set('closed');
			if (disposed) return;
			const backoff = Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempt++);
			retryTimer = setTimeout(open, backoff);
		};
	}

	open();
	return () => {
		disposed = true;
		if (pingTimer) clearInterval(pingTimer);
		if (retryTimer) clearTimeout(retryTimer);
		ws?.close();
	};
}
