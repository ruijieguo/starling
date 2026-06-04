<script lang="ts">
	import { api } from '$lib/api';
	import DataTable from '$lib/components/DataTable.svelte';

	type Commit = { rows: Record<string, unknown>[] };
	let rows = $state<Record<string, unknown>[]>([]);
	let err = $state('');

	async function load() {
		try {
			const d = await api.get<Commit>('/api/commitments');
			rows = d.rows.filter((r) => r.state === 'ACTIVE' || r.state === 'created');
			err = '';
		} catch (e) {
			err = String(e);
		}
	}

	$effect(() => {
		load();
	});
</script>

<h1 class="text-xl font-semibold mb-4">承诺提醒（pending / ACTIVE）</h1>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
{#if rows.length}
	<DataTable {rows} columns={['state', 'subject_id', 'predicate', 'object_value', 'deadline']} />
{:else}<p class="text-sm text-zinc-500">无待办承诺。</p>{/if}
