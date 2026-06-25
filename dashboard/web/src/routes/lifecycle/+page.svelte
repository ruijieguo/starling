<script lang="ts">
	import { api, type LifecycleResponse } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Card, Badge, EmptyState, Skeleton } from '$lib/components/ui';
	import {
		occupancyStages,
		transitionFlows,
		consolidationDriven,
		stageLabel,
		type Tone
	} from '$lib/lifecycle';

	const q = createQuery(() => api.get<LifecycleResponse>('/api/lifecycle'));
	$effect(() => {
		q.refetch();
	});

	let occ = $derived(q.data?.occupancy ?? {});
	let ev = $derived(q.data?.events ?? {});
	let snapshot = $derived(occupancyStages(occ));
	let flows = $derived(transitionFlows(ev, occ));
	let driven = $derived(consolidationDriven(ev));

	// tone → 比例条/图例填色(app.css @theme 注册的色 token)。
	const FILL: Record<Tone, string> = {
		info: 'bg-info',
		brand: 'bg-brand',
		success: 'bg-success',
		neutral: 'bg-subtle',
		danger: 'bg-danger',
		warn: 'bg-warn'
	};
</script>

<PageHeader
	title="生命周期"
	subtitle="记忆从短期(海马)经固化进入长期(新皮层),再归档或遗忘。当前分布为精确快照,流转为事件派生的累计量。"
/>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<Skeleton class="h-40 w-full" />
{:else if q.data}
	<div class="space-y-4">
		<Card title="当前分布" description="按 consolidation_state 的精确快照(tenant-scoped)。">
			{#if snapshot.total === 0}
				<EmptyState title="记忆库为空" description="还没有任何语句。remember / converse 之后这里会出现分布。" />
			{:else}
				<div class="flex h-3 w-full overflow-hidden rounded-control border border-border">
					{#each snapshot.stages as st (st.key)}
						{#if st.count > 0}
							<div
								class="{FILL[st.tone]} h-full"
								style="width:{st.pct}%"
								title="{st.label} · {st.count}"
							></div>
						{/if}
					{/each}
				</div>
				<dl class="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-5">
					{#each snapshot.stages as st (st.key)}
						<div>
							<dt class="flex items-center gap-1.5 text-xs text-subtle">
								<span class="inline-block size-2 rounded-full {FILL[st.tone]}"></span>{st.label}
							</dt>
							<dd class="mt-0.5 text-sm font-medium text-fg">{st.count}</dd>
						</div>
					{/each}
				</dl>
				<p class="mt-2 text-xs text-subtle">共 {snapshot.total} 条</p>
			{/if}
		</Card>

		<Card
			title="流转(累计)"
			description="多数从 typed bus 事件派生;遗忘为终态快照(forget 不产事件)。零状态转移审计表——boring-by-default,从既有 statements + bus_events 派生。"
		>
			{#if !driven}
				<p
					class="mb-2 rounded-control border border-dashed border-border bg-bg px-3 py-2 text-xs text-subtle"
				>
					固化通道尚未明显驱动:SLEEP/IDLE 回放暂无调用方,只有 ONLINE 随手固化会累计 statement.consolidated。
				</p>
			{/if}
			<ul class="space-y-2">
				{#each flows as f (f.key)}
					<li
						class="flex items-center justify-between gap-3 rounded-control border border-border bg-surface px-4 py-2.5"
					>
						<div class="flex min-w-0 items-center gap-2">
							<span class="text-sm text-fg">{f.label}</span>
							<span class="text-xs text-subtle">→ {stageLabel(f.target)}</span>
							{#if f.source === 'snapshot'}<Badge tone="neutral">快照</Badge>{/if}
						</div>
						<span class="shrink-0 text-sm font-medium text-fg">{f.count}</span>
					</li>
				{/each}
			</ul>
		</Card>
	</div>
{/if}
