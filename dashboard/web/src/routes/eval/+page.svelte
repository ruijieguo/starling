<script lang="ts">
	import { api } from '$lib/api';

	type Reports = { reports: { name: string; markdown: string }[] };
	let data = $state<Reports | null>(null);
	let err = $state('');
	$effect(() => {
		api
			.get<Reports>('/api/eval')
			.then((d) => (data = d))
			.catch((e) => (err = String(e)));
	});
</script>

<h1 class="text-xl font-semibold mb-4">Eval 报告</h1>
{#if err}<p class="text-red-500 text-sm">{err}</p>{/if}
{#if data}
	{#each data.reports as r}
		<details class="mb-3 rounded-lg border border-zinc-200 dark:border-zinc-800 p-3" open>
			<summary class="cursor-pointer font-medium">{r.name}</summary>
			<pre class="mt-2 text-xs whitespace-pre-wrap font-mono">{r.markdown}</pre>
		</details>
	{/each}
{/if}
