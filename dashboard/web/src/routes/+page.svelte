<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import { lastWsEvent } from '$lib/health';
	import StatCard from '$lib/components/StatCard.svelte';
	import { Card, Skeleton, EmptyState } from '$lib/components/ui';

	type Overview = {
		counts: Record<string, number>;
		commitments_by_state: Record<string, number>;
		queue_by_status: Record<string, number>;
	};
	const q = createQuery(() => api.get<Overview>('/api/overview'));
	$effect(() => {
		q.refetch();
	});
	$effect(() => {
		const e = $lastWsEvent;
		if (e && (e.type === 'tick' || e.type === 'statement_added')) q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">总览</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="grid grid-cols-2 gap-3 md:grid-cols-3">
		{#each Array(6) as _}<Skeleton class="h-20 w-full" />{/each}
	</div>
{:else if q.data}
	<div class="space-y-6">
		<div class="grid grid-cols-2 gap-3 md:grid-cols-3">
			{#each Object.entries(q.data.counts) as [k, v]}<StatCard label={k} value={v} />{/each}
		</div>
		<Card title="承诺分态">
			<div class="grid grid-cols-3 gap-3 md:grid-cols-6">
				{#each Object.entries(q.data.commitments_by_state) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
		<Card title="队列状态">
			<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
				{#each Object.entries(q.data.queue_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
	</div>
{/if}
