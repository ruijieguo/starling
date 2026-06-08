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

	async function refetch() {
		loading = true;
		try {
			data = await fetcher();
			error = null;
		} catch (e) {
			error = e instanceof ApiError ? e : new ApiError(0, '', String(e));
		} finally {
			loading = false;
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
