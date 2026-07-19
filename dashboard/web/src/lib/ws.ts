import { getToken } from './token';
import { wsConn } from './health';

/**
 * 广播 /ws 的事件词表 —— 与后端一一对应:routes/commands.py 的六处 _broadcast
 * (statement_added / statement_forgotten / recall / tick / commitment_fired /
 * commitment_transition)+ app.py 后台循环的 tick + converse 流完结后补广播的
 * statement_added。lib/feed.ts 的 switch 也正好覆盖这六种。
 *
 * 收窄为联合类型而非 string:页面里的事件名字面量此前完全不受 svelte-check 校验,
 * 打错一个字母就是静默失效且三门全绿(T8 review M3)。注意 /ws/converse 是另一条
 * socket、另一套 type(token/done/error),由 streamConverse 自带类型处理,不属此表。
 */
export const WS_EVENT_TYPES = [
	'tick',
	'statement_added',
	'statement_forgotten',
	'recall',
	'commitment_transition',
	'commitment_fired'
] as const;
export type WsEventType = (typeof WS_EVENT_TYPES)[number];

export type WsEvent = { type: WsEventType; payload: unknown };

/**
 * 这一帧是否可能改变了记忆库的可见状态 —— 各只读页统一用它作增量刷新的判据。
 *
 * 六种事件里只有 recall 是纯读(planned_recall 不写库,广播只为总览 feed 记一笔),
 * 其余五种要么是写入、要么是后台推进,都可能改变任一页展示的内容。
 *
 * 为什么不按页精确列事件集(T8 review I1/I2/I3/M1 的教训):那样列过一版,六页里四页
 * 列漏了 —— 漏的都是隐蔽的跨域因果,例如
 *   · 承诺的「创建」走写入路径而非 tick(subscriber_pump.cpp 的 run_post_write 每次写入
 *     都跑 policy_engine → create_from_statement → upsert_active_commitment),
 *     所以只订 commitment_* + tick 的看板,新许下的承诺要等下一次 tick 才出现;
 *   · 嵌入积压在语句落库瞬间 +1,但 post-write pump 没有 embed 阶段,只订 tick 要等 30s;
 *   · 冲突页拿 src_state/dst_state 既过滤行又决定按钮显隐,而这两个 state 由后台 tick 改。
 * 收益(省掉一次只读 GET)极小 —— SPA 同时只挂载一个路由页;代价(显示陈旧数据,且用户
 * 无从察觉)极大。故不做这个优化,统一判据。
 */
export const mutatesMemory = (e: WsEvent | null | undefined): boolean =>
	!!e && e.type !== 'recall';

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
