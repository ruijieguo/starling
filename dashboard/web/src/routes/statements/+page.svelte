<script lang="ts">
	import { api } from '$lib/api';
	import DataTable from '$lib/components/DataTable.svelte';

	let predicate = $state('');
	let perspective = $state('');
	let rows = $state<Record<string, unknown>[]>([]);
	let err = $state('');

	async function load() {
		try {
			const q = new URLSearchParams();
			if (predicate) q.set('predicate', predicate);
			if (perspective) q.set('perspective', perspective);
			const d = await api.get<{ rows: Record<string, unknown>[] }>(`/api/statements?${q}`);
			rows = d.rows;
			err = '';
		} catch (e) {
			err = String(e);
		}
	}

	$effect(() => {
		load();
	});
</script>

<h1 class="text-xl font-semibold mb-4">Statements</h1>
<div class="flex gap-2 mb-3">
	<input
		bind:value={predicate}
		placeholder="predicate"
		class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"
	/>
	<input
		bind:value={perspective}
		placeholder="perspective"
		class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"
	/>
	<button
		onclick={load}
		class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm"
		>筛选</button
	>
</div>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
<DataTable
	{rows}
	columns={[
		'holder_id',
		'holder_perspective',
		'subject_id',
		'predicate',
		'object_value',
		'modality',
		'polarity'
	]}
/>
