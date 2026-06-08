import { ApiError } from './api';

export type QueryState<T> = {
	readonly data: T | null;
	readonly error: ApiError | null;
	readonly loading: boolean;
	refetch: () => Promise<void>;
};

/**
 * 统一的"载入/空/错"数据原语。传入一个返回 Promise 的 fetcher;
 * 组件读 `q.loading / q.error / q.data` 三态,调 `q.refetch()` 重取。
 * 用 Svelte 5 runes($state),文件名须 `.svelte.ts`。
 */
export function createQuery<T>(fetcher: () => Promise<T>): QueryState<T> {
	let data = $state<T | null>(null);
	let error = $state<ApiError | null>(null);
	let loading = $state(false);
	// 单调代号:并发 refetch 时只让最新一次结果落地,丢弃过期(乱序)响应。
	let gen = 0;

	async function refetch() {
		const myGen = ++gen;
		loading = true;
		try {
			const d = await fetcher();
			if (myGen !== gen) return; // 已被更晚的 refetch 取代
			data = d;
			error = null;
		} catch (e) {
			if (myGen !== gen) return;
			error = e instanceof ApiError ? e : new ApiError(0, '', String(e));
		} finally {
			if (myGen === gen) loading = false;
		}
	}

	return {
		get data() {
			return data;
		},
		get error() {
			return error;
		},
		get loading() {
			return loading;
		},
		refetch
	};
}
