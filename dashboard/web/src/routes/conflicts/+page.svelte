<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import { Badge, Card, EmptyState, Skeleton } from '$lib/components/ui';

	type Conflict = { src_id: string; dst_id: string; edge_kind: string; weight: number };
	type ConflictData = { by_kind: Record<string, number>; conflicts: Conflict[] };

	const q = createQuery(() => api.get<ConflictData>('/api/conflicts'));
	$effect(() => {
		q.refetch();
	});

	let sorted = $derived(
		[...(q.data?.conflicts ?? [])].sort((a, b) => b.weight - a.weight)
	);

	let maxWeight = $derived(sorted.length > 0 ? Math.max(...sorted.map((c) => c.weight)) : 1);

	function barWidth(weight: number, max: number): string {
		if (weight <= 1) return `${Math.min(100, weight * 100)}%`;
		return `${Math.min(100, (weight / max) * 100)}%`;
	}
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">ConflictProbe</h1>

{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="space-y-2">
		{#each Array(4) as _}<Skeleton class="h-10 w-full" />{/each}
	</div>
{:else}
	{#if q.data}
		<div class="mb-4 flex flex-wrap gap-2">
			{#each Object.entries(q.data.by_kind) as [k, v]}
				<Badge tone={v ? 'warn' : 'neutral'}>{k}: {v}</Badge>
			{/each}
		</div>
	{/if}

	{#if sorted.length === 0}
		<EmptyState title="无冲突" />
	{:else}
		<Card>
			<ul class="divide-y divide-border">
				{#each sorted as c}
					<li class="flex items-center gap-3 py-2.5">
						<span class="w-32 shrink-0 truncate text-xs font-medium text-fg" title={c.src_id}>{c.src_id}</span>
						<span class="text-xs text-subtle">→</span>
						<span class="w-32 shrink-0 truncate text-xs text-fg" title={c.dst_id}>{c.dst_id}</span>
						<Badge tone="warn">{c.edge_kind}</Badge>
						<div class="flex flex-1 items-center gap-2">
							<div class="h-2 flex-1 overflow-hidden rounded-full bg-surface">
								<div
									class="h-full rounded-full bg-brand transition-all"
									style="width: {barWidth(c.weight, maxWeight)}"
								></div>
							</div>
							<span class="w-12 text-right text-xs text-muted">{c.weight}</span>
						</div>
					</li>
				{/each}
			</ul>
		</Card>
	{/if}
{/if}
