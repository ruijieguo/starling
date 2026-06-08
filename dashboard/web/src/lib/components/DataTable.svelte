<script lang="ts">
	import EmptyState from './ui/EmptyState.svelte';
	import Skeleton from './ui/Skeleton.svelte';
	import Input from './ui/Input.svelte';

	let {
		rows = [],
		columns,
		loading = false,
		emptyText = '无数据',
		pageSize = 12,
		filterable = true
	}: {
		rows?: Record<string, unknown>[];
		columns: string[];
		loading?: boolean;
		emptyText?: string;
		pageSize?: number;
		filterable?: boolean;
	} = $props();

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
	let sorted = $derived(
		sortCol
			? [...filtered].sort((a, b) => {
					const av = fmt(a[sortCol]);
					const bv = fmt(b[sortCol]);
					return av < bv ? -sortDir : av > bv ? sortDir : 0;
				})
			: filtered
	);
	let pageCount = $derived(Math.max(1, Math.ceil(sorted.length / pageSize)));
	let pageRows = $derived(sorted.slice(page * pageSize, page * pageSize + pageSize));
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
			<Input bind:value={filter} placeholder="筛选…" oninput={() => (page = 0)} />
		</div>
	{/if}
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
					<tr class="border-t border-border/60">
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
