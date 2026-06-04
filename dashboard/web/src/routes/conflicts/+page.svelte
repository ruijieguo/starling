<script lang="ts">
	import { api } from '$lib/api';
	import DataTable from '$lib/components/DataTable.svelte';

	type ConflictData = {
		by_kind: Record<string, number>;
		conflicts: Record<string, unknown>[];
	};
	let d = $state<ConflictData | null>(null);
	let err = $state('');

	async function load() {
		try { d = await api.get<ConflictData>('/api/conflicts'); err = ''; }
		catch (e) { err = String(e); }
	}
	$effect(() => { load(); });
</script>

<h1 class="text-xl font-semibold mb-4">ConflictProbe</h1>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
{#if d}
	<div class="flex gap-2 mb-4 text-xs flex-wrap">
		{#each Object.entries(d.by_kind) as [k, v]}
			<span class="px-2 py-1 rounded-lg border border-zinc-200 dark:border-zinc-800">{k}: {v}</span>
		{/each}
	</div>
	<DataTable rows={d.conflicts} columns={['src_id', 'dst_id', 'edge_kind', 'weight']} />
{/if}
