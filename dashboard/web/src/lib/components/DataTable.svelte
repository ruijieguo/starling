<script lang="ts">
	import EmptyState from './ui/EmptyState.svelte';
	import Skeleton from './ui/Skeleton.svelte';
	import Input from './ui/Input.svelte';
	// 相对路径(非 $lib):vitest.config.ts 未过 SvelteKit 插件,$lib alias 在 vitest
	// 下无法解析,值级 $lib 导入会让本组件的 .test.ts 整个 suite 挂掉。勿改回 $lib。
	import { density, pageSizeFor } from '../ui/density';

	let {
		rows = [],
		columns,
		loading = false,
		emptyText = '无数据',
		pageSize,
		filterable = true,
		onRowClick
	}: {
		rows?: Record<string, unknown>[];
		columns: string[];
		loading?: boolean;
		emptyText?: string;
		pageSize?: number;
		filterable?: boolean;
		onRowClick?: (row: Record<string, unknown>) => void;
	} = $props();

	// 未显式传 pageSize 时,跟随全局密度(宽松/紧凑),见 lib/ui/density.ts。
	let effectivePageSize = $derived(pageSize ?? pageSizeFor($density));

	let sortCol = $state('');
	let sortDir = $state<1 | -1>(1);
	let filter = $state('');
	let page = $state(0);

	function fmt(v: unknown): string {
		if (v === null || v === undefined) return '';
		if (typeof v === 'object') return JSON.stringify(v);
		return String(v);
	}

	function toggleSort(c: string) {
		if (sortCol === c) sortDir = sortDir === 1 ? -1 : 1;
		else {
			sortCol = c;
			sortDir = 1;
		}
		page = 0;
	}

	let filtered = $derived(
		filter.trim()
			? rows.filter((r) => columns.some((c) => fmt(r[c]).toLowerCase().includes(filter.toLowerCase())))
			: rows
	);
	// 自然排序:数字列按数值比(localeCompare numeric),"10" 排在 "2" 之后,
	// 不再字典序错排;字符串与 ISO 日期照常正确。
	let sorted = $derived(
		sortCol
			? [...filtered].sort(
					(a, b) =>
						sortDir * fmt(a[sortCol]).localeCompare(fmt(b[sortCol]), undefined, { numeric: true })
				)
			: filtered
	);
	let pageCount = $derived(Math.max(1, Math.ceil(sorted.length / effectivePageSize)));
	let pageRows = $derived(
		sorted.slice(page * effectivePageSize, page * effectivePageSize + effectivePageSize)
	);

	// 外部数据(rows 引用)或每页行数(密度切换 → effectivePageSize)变化时回到第 1 页,
	// 避免停在越界空页(如停第 4 页时切紧凑使总页数变 2,page=3 会 slice 出空数组)。
	$effect(() => {
		void rows;
		void effectivePageSize;
		page = 0;
	});
</script>

{#if loading}
	<div class="space-y-2">
		{#each Array(4) as _}<Skeleton class="h-8 w-full" />{/each}
	</div>
{:else if rows.length === 0}
	<EmptyState title={emptyText} />
{:else}
	{#if filterable}
		<div class="mb-2 max-w-xs">
			<Input bind:value={filter} placeholder="筛选…" aria-label="筛选" oninput={() => (page = 0)} />
		</div>
	{/if}
	{#if sorted.length === 0}
		<p class="px-1 py-2 text-sm text-subtle">无匹配结果</p>
	{:else}
		<div class="overflow-x-auto rounded-lg border border-border">
			<table class="w-full text-sm">
				<thead class="bg-surface text-left">
					<tr>
						{#each columns as c}
							<th scope="col" aria-sort={sortCol === c ? (sortDir === 1 ? 'ascending' : 'descending') : 'none'} class="px-3 py-2 font-medium text-muted">
								<button class="inline-flex items-center gap-1 hover:text-fg" onclick={() => toggleSort(c)}>
									{c}{#if sortCol === c}<span aria-hidden="true">{sortDir === 1 ? '↑' : '↓'}</span>{/if}
								</button>
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each pageRows as r}
						<tr
							class="border-t border-border/60 {onRowClick ? 'cursor-pointer hover:bg-surface' : ''}"
							role={onRowClick ? 'button' : undefined}
							tabindex={onRowClick ? 0 : undefined}
							onclick={onRowClick ? () => onRowClick(r) : undefined}
							onkeydown={onRowClick
								? (e) => {
										if (e.key === 'Enter' || e.key === ' ') {
											e.preventDefault();
											onRowClick(r);
										}
									}
								: undefined}
						>
							{#each columns as c}<td class="px-3" style="padding-block: var(--row-py)">{fmt(r[c])}</td>{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if pageCount > 1}
			<div class="mt-2 flex items-center justify-between text-xs text-muted">
				<span>{sorted.length} 行 · 第 {page + 1}/{pageCount} 页</span>
				<div class="flex gap-1">
					<button class="rounded border border-border px-2 py-1 disabled:opacity-40" disabled={page === 0} onclick={() => (page = Math.max(0, page - 1))}>上一页</button>
					<button class="rounded border border-border px-2 py-1 disabled:opacity-40" disabled={page >= pageCount - 1} onclick={() => (page = Math.min(pageCount - 1, page + 1))}>下一页</button>
				</div>
			</div>
		{/if}
	{/if}
{/if}
