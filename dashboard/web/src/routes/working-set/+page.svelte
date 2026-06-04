<script lang="ts">
	import { api } from '$lib/api';

	let interlocutor = $state('Alice');
	let goal = $state('');
	let ws = $state<{
		render: string;
		blocks: { label: string; content: string; tokens: number }[];
		truncated: string[];
	} | null>(null);
	let err = $state('');

	async function load() {
		try {
			const q = new URLSearchParams({ interlocutor });
			if (goal) q.set('goal', goal);
			ws = await api.get(`/api/working_set?${q}`);
			err = '';
		} catch (e) {
			err = String(e);
		}
	}
</script>

<h1 class="text-xl font-semibold mb-4">Working Set</h1>
<div class="flex gap-2 mb-3">
	<input
		bind:value={interlocutor}
		class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"
		placeholder="interlocutor"
	/>
	<input
		bind:value={goal}
		class="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm"
		placeholder="goal (optional)"
	/>
	<button
		onclick={load}
		class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm"
		>渲染</button
	>
</div>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
{#if ws}
	<div class="text-xs text-zinc-500 mb-2">
		blocks: {ws.blocks.map((b) => `${b.label}(${b.tokens})`).join(' · ')}{ws.truncated.length
			? ` · truncated: ${ws.truncated.join(',')}`
			: ''}
	</div>
	<pre
		class="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3 text-xs whitespace-pre-wrap font-mono">{ws.render}</pre>
{/if}
