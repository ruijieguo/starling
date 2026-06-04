<script lang="ts">
	import { api } from '$lib/api';
	import Graph from '$lib/components/Graph.svelte';
	import DataTable from '$lib/components/DataTable.svelte';

	type Cognizer = { id: string; canonical_name: string; kind: string; last_seen_at: string };
	type Relation = { a_id: string; b_id: string; affinity: number; power_asymmetry: number };
	let d = $state<{ nodes: Cognizer[]; relations: Relation[] } | null>(null);
	let err = $state('');

	$effect(() => {
		api
			.get<{ nodes: Cognizer[]; relations: Relation[] }>('/api/cognizers')
			.then((x) => (d = x))
			.catch((e) => (err = String(e)));
	});

	let gnodes = $derived((d?.nodes ?? []).map((n) => ({ id: n.id, label: n.canonical_name })));
	let gedges = $derived((d?.relations ?? []).map((r) => ({ a: r.a_id, b: r.b_id })));
</script>

<h1 class="text-xl font-semibold mb-4">Cognizer 社会图</h1>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
{#if d}
	<Graph nodes={gnodes} edges={gedges} />
	<h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">节点</h2>
	<DataTable rows={d.nodes} columns={['canonical_name', 'kind', 'last_seen_at']} />
{/if}
