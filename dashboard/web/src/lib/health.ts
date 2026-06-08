import { writable } from 'svelte/store';
import type { WsEvent } from './ws';

export type Conn = 'connecting' | 'open' | 'closed';
/** WebSocket 连接态(壳顶健康灯之一)。 */
export const wsConn = writable<Conn>('closed');
/** LLM / Embedder 是否已配置(null=未知)。 */
export const llmConfigured = writable<boolean | null>(null);
export const embedderConfigured = writable<boolean | null>(null);
/** 壳层单一 ws 连接广播的最近一帧事件;各页面订阅它做增量刷新。 */
export const lastWsEvent = writable<WsEvent | null>(null);
