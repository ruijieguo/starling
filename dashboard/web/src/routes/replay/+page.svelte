<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import { Card, EmptyState } from '$lib/components/ui';

	type ReplayData = {
		scheduler: Record<string, unknown>;
		ledger: Record<string, unknown>[];
		windows: Record<string, unknown>[];
	};
	const q = createQuery(() => api.get<ReplayData>('/api/replay'));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Replay / Reconsolidation</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.data}
	<div class="space-y-4">
		<Card title="调度器">
			<CodeBlock content={JSON.stringify(q.data.scheduler)} language="json" collapsible />
		</Card>
		<div>
			<h2 class="mb-2 text-sm font-semibold text-muted">Ledger</h2>
			<DataTable
				rows={q.data.ledger}
				emptyText="无 ledger"
				columns={['replay_batch_id', 'mode', 'sampled_count', 'started_at', 'finished_at']}
			/>
		</div>
		<div>
			<h2 class="mb-2 text-sm font-semibold text-muted">再巩固窗口</h2>
			<DataTable
				rows={q.data.windows}
				emptyText="无窗口"
				columns={['stmt_id', 'opened_at', 'close_deadline', 'status']}
			/>
		</div>
	</div>
{/if}
