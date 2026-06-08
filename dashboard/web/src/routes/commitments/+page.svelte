<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Badge, EmptyState } from '$lib/components/ui';

	const STATES = ['created', 'ACTIVE', 'FULFILLED', 'BROKEN', 'RENEGOTIATED', 'WITHDRAWN'];
	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>('/api/commitments'));
	$effect(() => {
		q.refetch();
	});
	let byState = $derived(
		STATES.map((s) => ({ s, n: (q.data?.rows ?? []).filter((r) => r.state === s).length }))
	);
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Commitment 五态机</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else}
	<div class="mb-4 flex flex-wrap gap-2">
		{#each byState as b}<Badge tone={b.n ? 'brand' : 'neutral'}>{b.s}: {b.n}</Badge>{/each}
	</div>
	<DataTable
		rows={q.data?.rows ?? []}
		loading={q.loading}
		emptyText="无 commitment"
		columns={['state', 'subject_id', 'predicate', 'object_value', 'broken_count', 'deadline', 'updated_at']}
	/>
{/if}
