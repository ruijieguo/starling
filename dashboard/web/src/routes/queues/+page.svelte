<script lang="ts">
	import { api } from '$lib/api';
	import StatCard from '$lib/components/StatCard.svelte';

	type QueueData = {
		dispatch: Record<string, number>;
		embedding_backlog: number;
		vectors_by_status: Record<string, number>;
	};
	let d = $state<QueueData | null>(null);
	let err = $state('');

	async function load() {
		try { d = await api.get<QueueData>('/api/queues'); err = ''; }
		catch (e) { err = String(e); }
	}
	$effect(() => { load(); });
</script>

<h1 class="text-xl font-semibold mb-4">队列 / 运维</h1>
{#if err}<p class="text-red-500 text-sm mb-2">{err}</p>{/if}
{#if d}
	<StatCard label="embedding backlog" value={d.embedding_backlog} />
	<h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">Outbox dispatch</h2>
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		{#each Object.entries(d.dispatch) as [k, v]}<StatCard label={k} value={v} />{/each}
	</div>
	<h2 class="text-sm font-semibold mt-4 mb-2 text-zinc-500">向量状态</h2>
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		{#each Object.entries(d.vectors_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
	</div>
{/if}
