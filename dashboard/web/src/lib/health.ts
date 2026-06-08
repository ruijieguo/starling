import { writable } from 'svelte/store';

export type Conn = 'connecting' | 'open' | 'closed';
/** WebSocket 连接态(壳顶健康灯之一)。 */
export const wsConn = writable<Conn>('closed');
/** LLM / Embedder 是否已配置(null=未知)。 */
export const llmConfigured = writable<boolean | null>(null);
export const embedderConfigured = writable<boolean | null>(null);
