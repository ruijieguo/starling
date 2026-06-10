<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Badge, Card, EmptyState, Skeleton, Drawer } from '$lib/components/ui';

	type Conflict = {
		src_id: string;
		dst_id: string;
		edge_kind: string;
		weight: number;
		metadata_json?: string;
		src_subject?: string;
		src_predicate?: string;
		src_object?: string;
		dst_subject?: string;
		dst_predicate?: string;
		dst_object?: string;
	};
	type ConflictData = { by_kind: Record<string, number>; conflicts: Conflict[] };

	const q = createQuery(() => api.get<ConflictData>('/api/conflicts'));
	$effect(() => {
		q.refetch();
	});

	let sorted = $derived([...(q.data?.conflicts ?? [])].sort((a, b) => b.weight - a.weight));
	let maxWeight = $derived(sorted.length ? Math.max(...sorted.map((c) => c.weight)) : 1);
	const barWidth = (w: number, max: number) =>
		w <= 1 ? `${Math.min(100, w * 100)}%` : `${Math.min(100, (w / max) * 100)}%`;

	const label = (subj?: string, pred?: string, obj?: string, fallback = '') =>
		subj || pred || obj ? `${subj ?? '?'} ${pred ?? ''} ${obj ?? ''}`.replace(/\s+/g, ' ').trim() : fallback;
	const reason = (m?: string) => {
		try {
			return m ? (JSON.parse(m).reason ?? '') : '';
		} catch {
			return '';
		}
	};

	let detailOpen = $state(false);
	let detail = $state<Conflict | null>(null);
	function openDetail(c: Conflict) {
		detail = c;
		detailOpen = true;
	}
</script>

<PageHeader title="冲突探针" subtitle="ConflictProbe:互斥语句对,按冲突权重降序。" />

{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="space-y-2">{#each Array(4) as _}<Skeleton class="h-12 w-full" />{/each}</div>
{:else}
	{#if q.data}
		<div class="mb-4 flex flex-wrap gap-2">
			{#each Object.entries(q.data.by_kind) as [k, v]}
				<Badge tone={k === 'CONFLICTS_WITH' ? 'danger' : 'neutral'}>{k}: {v}</Badge>
			{/each}
		</div>
	{/if}

	{#if sorted.length === 0}
		<EmptyState title="无冲突" description="没有 CONFLICTS_WITH 边。" />
	{:else}
		<Card>
			<ul class="divide-y divide-border">
				{#each sorted as c}
					<li>
						<button
							type="button"
							onclick={() => openDetail(c)}
							class="flex w-full items-center gap-3 py-2.5 text-left transition hover:opacity-80"
						>
							<div class="min-w-0 flex-1">
								<div class="truncate text-sm text-fg">
									<span class="font-medium"
										>{label(c.src_subject, c.src_predicate, c.src_object, c.src_id.slice(0, 8))}</span
									>
									<span class="text-subtle"> ⚔ </span>
									<span>{label(c.dst_subject, c.dst_predicate, c.dst_object, c.dst_id.slice(0, 8))}</span>
								</div>
								{#if reason(c.metadata_json)}
									<div class="mt-0.5 truncate text-xs text-subtle">{reason(c.metadata_json)}</div>
								{/if}
							</div>
							<div class="flex w-40 shrink-0 items-center gap-2">
								<div class="h-2 flex-1 overflow-hidden rounded-full bg-surface">
									<div
										class="h-full rounded-full bg-brand"
										style="width: {barWidth(c.weight, maxWeight)}"
									></div>
								</div>
								<span class="w-9 text-right text-xs tabular-nums text-muted">{c.weight}</span>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		</Card>
	{/if}
{/if}

<Drawer bind:open={detailOpen} title="冲突详情">
	{#if detail}
		<div class="space-y-3 text-sm">
			<div>
				<div class="text-xs uppercase tracking-wide text-subtle">权重</div>
				<div class="text-fg">{detail.weight}</div>
			</div>
			{#if reason(detail.metadata_json)}
				<div>
					<div class="text-xs uppercase tracking-wide text-subtle">原因</div>
					<div class="text-fg">{reason(detail.metadata_json)}</div>
				</div>
			{/if}
			<div class="rounded-control border border-border bg-surface p-3">
				<div class="text-xs uppercase tracking-wide text-subtle">语句 A（src）</div>
				<div class="mt-1 text-fg">
					{label(detail.src_subject, detail.src_predicate, detail.src_object, '（已删除或缺失）')}
				</div>
				<div class="mt-1 break-all font-mono text-xs text-subtle">{detail.src_id}</div>
			</div>
			<div class="rounded-control border border-border bg-surface p-3">
				<div class="text-xs uppercase tracking-wide text-subtle">语句 B（dst）</div>
				<div class="mt-1 text-fg">
					{label(detail.dst_subject, detail.dst_predicate, detail.dst_object, '（已删除或缺失）')}
				</div>
				<div class="mt-1 break-all font-mono text-xs text-subtle">{detail.dst_id}</div>
			</div>
			<a href="/statements" class="inline-block text-xs text-brand hover:underline">
				在 Statements 中查看 →
			</a>
		</div>
	{/if}
</Drawer>
