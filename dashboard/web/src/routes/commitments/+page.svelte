<script lang="ts">
	import { api } from '$lib/api';
	import DataTable from '$lib/components/DataTable.svelte';

	const STATES = ['created', 'ACTIVE', 'FULFILLED', 'BROKEN', 'RENEGOTIATED', 'WITHDRAWN'];
	let rows = $state<Record<string, unknown>[]>([]);
	let err = $state('');

	async function load() {
		try { const d = await api.get<{ rows: Record<string, unknown>[] }>('/api/commitments'); rows = d.rows; err = ''; }
		catch (e) { err = String(e); }
	}
	$effect(() => { load(); });

	let byState = $derived(STATES.map((s) => ({ s, n: rows.filter((r) => r.state === s).length })));
</script>

<h1 class="text-xl font-semibold mb-4">Commitment 五态机</h1>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
<div class="flex gap-2 mb-4 text-xs flex-wrap">
	{#each byState as b}
		<span class="px-2 py-1 rounded-lg border border-zinc-200 dark:border-zinc-800">{b.s}: {b.n}</span
		>
	{/each}
</div>
<DataTable
	{rows}
	columns={['state', 'subject_id', 'predicate', 'object_value', 'broken_count', 'deadline', 'updated_at']}
/>
