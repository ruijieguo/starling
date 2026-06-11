import { getToken } from './token';

export class ApiError extends Error {
	constructor(
		public status: number,
		public path: string,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
	/** 401/403 → 多半是 token 缺失/失效。 */
	get isAuth(): boolean {
		return this.status === 401 || this.status === 403;
	}
}

const TIMEOUT_MS = 15000;

// 默认 15s 适用于本地读查询;走 LLM/embedder 网络的端点(remember/recall/
// working_set/config test/save/tick)真模型下要 20-45s 甚至更久,调用点用
// timeoutMs 按请求放宽——否则前端先报超时、后端继续完成,UI 与事实错位。
type ReqInit = RequestInit & { timeoutMs?: number };

async function req<T>(path: string, init: ReqInit = {}): Promise<T> {
	const { timeoutMs = TIMEOUT_MS, ...rest } = init;
	const headers = new Headers(rest.headers);
	const tok = getToken();
	if (tok) headers.set('Authorization', `Bearer ${tok}`);
	headers.set('Content-Type', 'application/json');
	const ctrl = new AbortController();
	const timer = setTimeout(() => ctrl.abort(), timeoutMs);
	// caller 传入的 signal 链到内部 controller:保证超时始终生效,且 caller 取消也能传播。
	if (rest.signal) {
		if (rest.signal.aborted) ctrl.abort();
		else rest.signal.addEventListener('abort', () => ctrl.abort(), { once: true });
	}
	try {
		const res = await fetch(path, { ...rest, headers, signal: ctrl.signal });
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				if (body?.detail) detail = String(body.detail);
			} catch {
				/* 非 JSON body,保留 statusText */
			}
			throw new ApiError(res.status, path, `${res.status} ${detail}`);
		}
		return (await res.json()) as T;
	} catch (e) {
		if (e instanceof ApiError) throw e;
		if (e instanceof DOMException && e.name === 'AbortError')
			throw new ApiError(0, path, `请求超时（>${timeoutMs / 1000}s）`);
		throw new ApiError(0, path, String(e));
	} finally {
		clearTimeout(timer);
	}
}

export const api = {
	get: <T>(p: string, init?: ReqInit) => req<T>(p, init),
	post: <T>(p: string, body: unknown, init?: ReqInit) =>
		req<T>(p, { ...init, method: 'POST', body: JSON.stringify(body) })
};
