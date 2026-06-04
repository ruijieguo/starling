<script lang="ts">
	import { api } from '$lib/api';
	import { connectWs } from '$lib/ws';
	import StatCard from '$lib/components/StatCard.svelte';

	type Overview = {
		counts: Record<string, number>;
		commitments_by_state: Record<string, number>;
		queue_by_status: Record<string, number>;
	};
	let data = $state<Overview | null>(null);
	let err = $state('');

	async function load() {
		try {
			data = await api.get<Overview>('/api/overview');
			err = '';
		} catch (e) {
			err = String(e);
		}
	}
	$effect(() => {
		load();
	});
	$effect(() => {
		const close = connectWs((e) => {
			if (e.type === 'tick' || e.type === 'statement_added') load();
		});
		return close;
	});
</script>

<h1 class="text-xl font-semibold mb-4">总览</h1>
{#if err}<p class="text-red-500 text-sm">{err}</p>{/if}
{#if data}
	<div class="grid grid-cols-2 md:grid-cols-3 gap-3">
		{#each Object.entries(data.counts) as [k, v]}<StatCard label={k} value={v} />{/each}
	</div>
	<h2 class="text-sm font-semibold mt-6 mb-2 text-zinc-500">承诺分态</h2>
	<div class="grid grid-cols-3 md:grid-cols-6 gap-3">
		{#each Object.entries(data.commitments_by_state) as [k, v]}<StatCard label={k} value={v} />{/each}
	</div>
	<h2 class="text-sm font-semibold mt-6 mb-2 text-zinc-500">队列状态</h2>
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		{#each Object.entries(data.queue_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
	</div>
{/if}
