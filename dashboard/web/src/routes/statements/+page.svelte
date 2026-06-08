<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Button, Input } from '$lib/components/ui';

	let predicate = $state('');
	let perspective = $state('');
	function url() {
		const p = new URLSearchParams();
		if (predicate) p.set('predicate', predicate);
		if (perspective) p.set('perspective', perspective);
		return `/api/statements?${p}`;
	}
	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>(url()));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Statements</h1>
<div class="mb-3 flex gap-2">
	<Input bind:value={predicate} placeholder="predicate" class="max-w-40" />
	<Input bind:value={perspective} placeholder="perspective" class="max-w-40" />
	<Button variant="secondary" onclick={() => q.refetch()}>筛选</Button>
</div>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<DataTable
	rows={q.data?.rows ?? []}
	loading={q.loading}
	emptyText="无 statements"
	columns={['holder_id', 'holder_perspective', 'subject_id', 'predicate', 'object_value', 'modality', 'polarity']}
/>
