<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import Graph from '$lib/components/Graph.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Card } from '$lib/components/ui';

	type Cognizer = { id: string; canonical_name: string; kind: string; last_seen_at: string };
	type Relation = { a_id: string; b_id: string; affinity: number; power_asymmetry: number };
	const q = createQuery(() => api.get<{ nodes: Cognizer[]; relations: Relation[] }>('/api/cognizers'));
	$effect(() => {
		q.refetch();
	});
	let gnodes = $derived((q.data?.nodes ?? []).map((n) => ({ id: n.id, label: n.canonical_name })));
	let gedges = $derived((q.data?.relations ?? []).map((r) => ({ a: r.a_id, b: r.b_id })));
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Cognizer 社会图</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<div class="space-y-4">
	<Card>
		<Graph nodes={gnodes} edges={gedges} />
	</Card>
	<DataTable
		rows={q.data?.nodes ?? []}
		loading={q.loading}
		emptyText="无 cognizer"
		columns={['canonical_name', 'kind', 'last_seen_at']}
	/>
</div>
