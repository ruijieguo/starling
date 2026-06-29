<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import { lastWsEvent } from '$lib/health';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Card, Badge, Skeleton, EmptyState } from '$lib/components/ui';
	import { stateTone, isHealthy, type RuntimeHealthResponse } from '$lib/runtime_health';

	// D4 (/plan-design-review): reuse createQuery + existing WS tick refetch. No new WS event types.
	const q = createQuery(() => api.get<RuntimeHealthResponse>('/api/runtime_health'));
	$effect(() => {
		q.refetch();
	});
	$effect(() => {
		const e = $lastWsEvent;
		if (e && (e.type === 'tick' || e.type === 'statement_added')) q.refetch();
	});

	const healthy = $derived(q.data != null && isHealthy(q.data));
</script>

<PageHeader title="运行时健康" subtitle="RuntimeHealth 状态机 + 转换事件(只读)" />

{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<Skeleton class="h-24 w-full" />
{:else if q.data}
	<div class="space-y-6">
		<!-- D3: 当前状态 pill 是第一张/标题卡(层级锚点) -->
		<Card title="当前状态">
			<div class="flex items-center gap-2 py-2">
				<Badge tone={stateTone(q.data.status)}>{q.data.status}</Badge>
				{#if healthy}
					<span class="text-sm text-success">一切正常</span>
				{/if}
			</div>
		</Card>

		<!-- D3: 转换事件为次要卡片 -->
		<Card title="转换事件" description="最近的健康状态转换(最多 64 条)">
			{#if q.data.events.length}
				<ul class="divide-y divide-border">
					{#each [...q.data.events].reverse() as e}
						<li class="flex items-center gap-2 py-2 text-sm">
							<Badge tone={stateTone(e.previous_status)}>{e.previous_status}</Badge>
							<span>→</span>
							<Badge tone={stateTone(e.current_status)}>{e.current_status}</Badge>
							<span class="text-muted">{e.trigger}</span>
							{#if e.missing_capabilities.length}
								<span class="text-danger">缺: {e.missing_capabilities.join(', ')}</span>
							{/if}
						</li>
					{/each}
				</ul>
			{:else}
				<EmptyState title="暂无转换" description="启动后将记录第一次转换" />
			{/if}
		</Card>
	</div>
{/if}
