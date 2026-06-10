<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Card, EmptyState, Skeleton } from '$lib/components/ui';

	type ReplayData = {
		scheduler: Record<string, unknown>;
		ledger: Record<string, unknown>[];
		windows: Record<string, unknown>[];
	};
	const q = createQuery(() => api.get<ReplayData>('/api/replay'));
	$effect(() => {
		q.refetch();
	});

	const LABELS: Record<string, string> = {
		online_trigger_counter: '在线触发计数',
		last_online_run_at: '上次在线回放',
		last_idle_run_at: '上次空闲回放',
		last_sleep_run_at: '上次睡眠回放',
		last_updated_at: '更新于'
	};
	let sched = $derived(q.data?.scheduler ?? {});
	let schedEntries = $derived(Object.entries(sched).filter(([k]) => k !== 'id'));
	const fmt = (v: unknown) => (v == null || v === '' ? '—' : String(v));
</script>

<PageHeader title="回放与再巩固" subtitle="Replay / Reconsolidation:调度器状态、批次与窗口。" />
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<Skeleton class="h-40 w-full" />
{:else if q.data}
	<div class="space-y-4">
		<Card title="调度器状态" description="在线 / 空闲 / 睡眠通道的最近运行。">
			{#if schedEntries.length === 0}
				<p class="text-sm text-muted">无调度器状态</p>
			{:else}
				<dl class="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
					{#each schedEntries as [k, v]}
						<div>
							<dt class="text-xs text-subtle">{LABELS[k] ?? k}</dt>
							<dd class="mt-0.5 text-sm font-medium text-fg">{fmt(v)}</dd>
						</div>
					{/each}
				</dl>
			{/if}
		</Card>
		<div>
			<h2 class="mb-2 text-sm font-semibold text-muted">Ledger（回放批次）</h2>
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
