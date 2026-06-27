<script lang="ts">
	import { api, type Gist, type GistData } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Badge, Card, EmptyState, Skeleton } from '$lib/components/ui';

	// #38-C v2 可观测:固化 NORM gist 的只读检视(GET /api/gists)。
	const q = createQuery(() => api.get<GistData>('/api/gists'));
	$effect(() => {
		q.refetch();
	});

	let gists = $derived(q.data?.gists ?? []);
	let byState = $derived(q.data?.by_state ?? {});

	// consolidated=已验证晋升(live、可检索);volatile=未门控/惰性(不可检索);
	// archived/forgotten=出局(冲突仲裁/衰减/遗忘)。
	const stateTone = (s: string): 'success' | 'info' | 'neutral' =>
		s === 'consolidated' ? 'success' : s === 'volatile' ? 'info' : 'neutral';
	const pct = (conf: number) => `${Math.round(conf * 100)}%`;
	const triple = (g: Gist) =>
		`${g.subject_id} ${g.predicate} ${g.object_value}`.replace(/\s+/g, ' ').trim();
</script>

<PageHeader
	title="固化 gist"
	subtitle="NORM gist:多 holder 共识经 LLM 判定 + 门控固化的范式(provenance=consolidation_abstract,只读)。"
/>

{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="space-y-2">{#each Array(4) as _}<Skeleton class="h-16 w-full" />{/each}</div>
{:else}
	{#if Object.keys(byState).length}
		<div class="mb-4 flex flex-wrap gap-2">
			{#each Object.entries(byState) as [s, n]}
				<Badge tone={stateTone(s)}>{s}: {n}</Badge>
			{/each}
		</div>
	{/if}

	{#if gists.length === 0}
		<EmptyState
			title="暂无 gist"
			description="配置 consolidation LLM 角色并跑离线回放(run_sleep)后,经验证门控固化的共识范式会出现在这里。"
		/>
	{:else}
		<Card>
			<ul class="divide-y divide-border">
				{#each gists as g}
					<li class="py-3">
						<div class="flex items-start justify-between gap-3">
							<div class="min-w-0 flex-1">
								<!-- LLM 一句话渲染;无 LLM(确定性)gist 回退到结构化三元组。 -->
								<div class="text-sm text-fg">{g.consolidation_summary || triple(g)}</div>
								<div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-subtle">
									<span class="font-mono">{g.predicate}</span>
									<span aria-hidden="true">·</span>
									<span class="truncate">{g.object_value}</span>
									<span aria-hidden="true">·</span>
									<span>派生自 {g.derived_from.length} 条(depth {g.derived_depth})</span>
								</div>
							</div>
							<div class="flex shrink-0 flex-col items-end gap-1">
								<Badge tone={stateTone(g.consolidation_state)}>{g.consolidation_state}</Badge>
								<span class="text-xs tabular-nums text-muted">conf {pct(g.confidence)}</span>
							</div>
						</div>
					</li>
				{/each}
			</ul>
		</Card>
	{/if}
{/if}
