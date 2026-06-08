<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import { Card, Skeleton, EmptyState } from '$lib/components/ui';

	type QueueData = {
		dispatch: Record<string, number>;
		embedding_backlog: number;
		vectors_by_status: Record<string, number>;
	};
	const q = createQuery(() => api.get<QueueData>('/api/queues'));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">队列 / 运维</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
		{#each Array(4) as _}<Skeleton class="h-20 w-full" />{/each}
	</div>
{:else if q.data}
	<div class="space-y-6">
		<StatCard label="embedding backlog" value={q.data.embedding_backlog} hint="待嵌入语句数" />
		<Card title="Outbox dispatch">
			<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
				{#each Object.entries(q.data.dispatch) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
		<Card title="向量状态">
			<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
				{#each Object.entries(q.data.vectors_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
	</div>
{/if}
