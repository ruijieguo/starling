<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Badge, EmptyState } from '$lib/components/ui';

	type ConflictData = { by_kind: Record<string, number>; conflicts: Record<string, unknown>[] };
	const q = createQuery(() => api.get<ConflictData>('/api/conflicts'));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">ConflictProbe</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else}
	{#if q.data}
		<div class="mb-4 flex flex-wrap gap-2">
			{#each Object.entries(q.data.by_kind) as [k, v]}<Badge tone={v ? 'warn' : 'neutral'}>{k}: {v}</Badge>{/each}
		</div>
	{/if}
	<DataTable
		rows={q.data?.conflicts ?? []}
		loading={q.loading}
		emptyText="无冲突"
		columns={['src_id', 'dst_id', 'edge_kind', 'weight']}
	/>
{/if}
