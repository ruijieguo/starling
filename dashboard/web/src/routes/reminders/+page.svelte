<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';

	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>('/api/commitments'));
	$effect(() => {
		q.refetch();
	});
	let rows = $derived(
		(q.data?.rows ?? []).filter((r) => r.state === 'ACTIVE' || r.state === 'created')
	);
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">承诺提醒（pending / ACTIVE）</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<DataTable
	{rows}
	loading={q.loading}
	emptyText="无待办承诺"
	columns={['state', 'subject_id', 'predicate', 'object_value', 'deadline']}
/>
