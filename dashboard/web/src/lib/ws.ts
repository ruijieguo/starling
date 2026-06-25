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

import type { ConverseResponse } from './api';

export type ConverseStreamReq = {
	message: string;
	provider?: string;
	holder?: string;
	interlocutor?: string;
	k?: number;
};

export type ConverseStreamHandlers = {
	onToken: (delta: string) => void;
	onDone: (outcome: ConverseResponse) => void;
	onError: (code: string) => void;
};

/**
 * 流式 converse(#37):一次性连接 /ws/converse,鉴权(首帧 token)→ 发请求 →
 * 收 {type:token,delta} 增量 / {type:done,...outcome} / {type:error,error}。
 * 与广播 /ws 不同——这是 per-turn、per-client 的请求/响应流,完结即关闭(非重连)。
 * 返回 cancel 函数:调用即关闭(converse 服务端仍跑完并落库,只是不再收帧)。
 * onDone / onError 至多触发一次(settled 守卫,涵盖连接错误/中途关闭)。
 */
export function streamConverse(
	req: ConverseStreamReq,
	handlers: ConverseStreamHandlers
): () => void {
	const proto = location.protocol === 'https:' ? 'wss' : 'ws';
	const ws = new WebSocket(`${proto}://${location.host}/ws/converse`);
	let settled = false;
	const settle = (fn: () => void) => {
		if (settled) return;
		settled = true;
		fn();
	};
	ws.onopen = () => {
		const t = getToken();
		if (t) ws.send(t); // auth handshake: in-band token first (mirrors /ws)
		ws.send(JSON.stringify(req));
	};
	ws.onmessage = (m) => {
		let msg: { type?: string; delta?: string; error?: string } & Partial<ConverseResponse>;
		try {
			msg = JSON.parse(m.data);
		} catch {
			return; // ignore malformed frame
		}
		if (msg.type === 'token') {
			handlers.onToken(msg.delta ?? '');
		} else if (msg.type === 'done') {
			settle(() => handlers.onDone(msg as ConverseResponse));
			ws.close();
		} else if (msg.type === 'error') {
			settle(() => handlers.onError(msg.error ?? 'error'));
			ws.close();
		}
	};
	ws.onerror = () => settle(() => handlers.onError('ws_error'));
	ws.onclose = () => settle(() => handlers.onError('ws_closed'));
	return () => ws.close();
}
