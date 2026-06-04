<script lang="ts">
	import { api } from '$lib/api';
	import DataTable from '$lib/components/DataTable.svelte';

	type ReplayData = {
		scheduler: Record<string, unknown>;
		ledger: Record<string, unknown>[];
		windows: Record<string, unknown>[];
	};
	let d = $state<ReplayData | null>(null);
	let err = $state('');

	async function load() {
		try { d = await api.get<ReplayData>('/api/replay'); err = ''; }
		catch (e) { err = String(e); }
	}
	$effect(() => { load(); });
</script>

<h1 class="text-xl font-semibold mb-4">Replay / Reconsolidation</h1>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
{#if d}
	<h2 class="text-sm font-semibold mb-2 text-zinc-500">调度器</h2>
	<pre class="text-xs font-mono mb-4 rounded-lg border border-zinc-200 dark:border-zinc-800 p-3">{JSON.stringify(d.scheduler, null, 2)}</pre>
	<h2 class="text-sm font-semibold mb-2 text-zinc-500">Ledger</h2>
	<DataTable rows={d.ledger} columns={['replay_batch_id', 'mode', 'sampled_count', 'started_at', 'finished_at']} />
	<h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">再巩固窗口</h2>
	<DataTable rows={d.windows} columns={['stmt_id', 'opened_at', 'close_deadline', 'status']} />
{/if}
