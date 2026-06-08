<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import { Badge, Card, EmptyState, Skeleton } from '$lib/components/ui';

	type CommitmentRow = {
		state: string;
		subject_id: string;
		predicate: string;
		object_value: string;
		broken_count: number;
		deadline?: string | null;
		updated_at: string;
		fired?: boolean;
	};

	const STATES = ['created', 'ACTIVE', 'FULFILLED', 'BROKEN', 'RENEGOTIATED', 'WITHDRAWN'];

	const q = createQuery(() => api.get<{ rows: CommitmentRow[] }>('/api/commitments'));
	$effect(() => {
		q.refetch();
	});

	let byState = $derived(
		STATES.map((s) => ({
			s,
			rows: (q.data?.rows ?? []).filter((r) => r.state === s)
		}))
	);
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Commitment 五态机</h1>

{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
		{#each Array(6) as _}<Skeleton class="h-32 w-full" />{/each}
	</div>
{:else}
	<div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
		{#each byState as lane}
			<Card title="{lane.s} ({lane.rows.length})">
				{#if lane.rows.length === 0}
					<p class="text-sm text-muted">—</p>
				{:else}
					<ul class="space-y-2">
						{#each lane.rows as r}
							<li class="rounded-lg border border-border bg-surface px-3 py-2 text-xs">
								<div class="flex items-start justify-between gap-2">
									<span class="font-medium text-fg">{r.subject_id}</span>
									{#if r.fired}
										<Badge tone="warn">⚠ DUE</Badge>
									{/if}
								</div>
								<div class="mt-0.5 text-muted">
									{r.predicate} <span class="text-subtle">→</span> {r.object_value}
								</div>
								{#if r.deadline}
									<div class="mt-1 text-subtle">deadline: {r.deadline}</div>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</Card>
		{/each}
	</div>
{/if}
