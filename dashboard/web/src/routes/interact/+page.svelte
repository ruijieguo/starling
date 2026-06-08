<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { toast } from '$lib/ui/toast';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Button, Textarea, Input, Badge, Card } from '$lib/components/ui';

	let text = $state('');
	let query = $state('');
	let remembered = $state<string[]>([]);
	let outcome = $state('');
	let results = $state<Record<string, unknown>[]>([]);
	let recalled = $state(false);
	let busyR = $state(false);
	let busyQ = $state(false);

	async function remember() {
		busyR = true;
		try {
			const r = await api.post<{ statement_ids: string[]; outcome: string }>('/api/remember', { text });
			remembered = r.statement_ids;
			outcome = r.outcome;
			toast.success(`outcome: ${r.outcome} · ${r.statement_ids.length} statements`);
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busyR = false;
		}
	}
	async function recall() {
		busyQ = true;
		try {
			const r = await api.post<{ results: Record<string, unknown>[] }>('/api/recall', { query });
			results = r.results;
			recalled = true;
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busyQ = false;
		}
	}
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">交互</h1>
<div class="max-w-2xl space-y-4">
	<Card title="Remember">
		<div class="space-y-2">
			<Textarea bind:value={text} rows={3} placeholder="记一段话…" />
			<div class="flex items-center gap-3">
				<Button loading={busyR} onclick={remember}>记住</Button>
				{#if remembered.length}<span class="text-xs text-muted">{outcome} · {remembered.length} statements</span>{/if}
			</div>
			{#if remembered.length}
				<div class="flex flex-wrap gap-1">
					{#each remembered as id}<Badge tone="brand">{id}</Badge>{/each}
				</div>
			{/if}
		</div>
	</Card>
	<Card title="Recall">
		<div class="space-y-2">
			<div class="flex gap-2">
				<Input bind:value={query} placeholder="query" />
				<Button loading={busyQ} variant="secondary" onclick={recall}>检索</Button>
			</div>
			{#if recalled}
				<DataTable rows={results} emptyText="无召回结果" columns={['subject', 'predicate', 'object', 'score']} />
			{/if}
		</div>
	</Card>
</div>
