<script lang="ts">
	import { api } from '$lib/api';
	import DataTable from '$lib/components/DataTable.svelte';

	let text = $state('');
	let query = $state('');
	let remembered = $state<string[]>([]);
	let results = $state<Record<string, unknown>[]>([]);
	let msg = $state('');

	async function remember() {
		try {
			const r = await api.post<{ statement_ids: string[]; outcome: string }>('/api/remember', {
				text
			});
			remembered = r.statement_ids;
			msg = `outcome: ${r.outcome}`;
		} catch (e) {
			msg = String(e);
		}
	}

	async function recall() {
		try {
			const r = await api.post<{ results: Record<string, unknown>[] }>('/api/recall', { query });
			results = r.results;
			msg = '';
		} catch (e) {
			msg = String(e);
		}
	}
</script>

<h1 class="text-xl font-semibold mb-4">交互</h1>
<section class="mb-6 space-y-2">
	<h2 class="text-sm font-semibold text-zinc-500">Remember</h2>
	<textarea
		bind:value={text}
		rows="3"
		class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"
	></textarea>
	<button
		onclick={remember}
		class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm"
		>记住</button
	>
	<span class="text-xs text-zinc-500">{msg} · {remembered.length} statements</span>
</section>
<section class="space-y-2">
	<h2 class="text-sm font-semibold text-zinc-500">Recall</h2>
	<input
		bind:value={query}
		class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"
		placeholder="query"
	/>
	<button
		onclick={recall}
		class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm"
		>检索</button
	>
	{#if results.length}<DataTable
			rows={results}
			columns={['subject', 'predicate', 'object', 'score']}
		/>{/if}
</section>
