<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import { EmptyState } from '$lib/components/ui';

	type Reports = { reports: { name: string; markdown: string }[] };
	const q = createQuery(() => api.get<Reports>('/api/eval'));
	$effect(() => {
		q.refetch();
	});
	let reports = $derived([...(q.data?.reports ?? [])].reverse());
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Eval 报告</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if reports.length === 0}
	<EmptyState title="暂无报告" />
{:else}
	<div class="space-y-3">
		{#each reports as r}
			<div>
				<div class="mb-1 text-sm font-medium text-fg">{r.name}</div>
				<CodeBlock content={r.markdown} language="text" collapsible />
			</div>
		{/each}
	</div>
{/if}
