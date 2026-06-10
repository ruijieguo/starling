<script lang="ts">
	import { api } from '$lib/api';
	import { byDeadline, deriveFired } from '$lib/commitments';
	import { createQuery } from '$lib/query.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Badge, Card, EmptyState, Skeleton, Input, Drawer } from '$lib/components/ui';

	type CommitmentRow = {
		stmt_id: string;
		state: string;
		subject_id: string;
		predicate: string;
		object_value: string;
		broken_count: number;
		deadline?: string | null;
		updated_at: string;
	};
	type Trigger = { commitment_stmt_id: string; status: string };

	const STATES = ['created', 'ACTIVE', 'FULFILLED', 'BROKEN', 'RENEGOTIATED', 'WITHDRAWN'];

	const q = createQuery(() =>
		api.get<{ rows: CommitmentRow[]; triggers: Trigger[] }>('/api/commitments')
	);
	$effect(() => {
		q.refetch();
	});

	let filter = $state('');
	let firedSet = $derived(deriveFired(q.data?.triggers));
	let rows = $derived(
		(q.data?.rows ?? [])
			.map((r) => ({ ...r, fired: firedSet.has(r.stmt_id) }))
			.filter((r) => {
				const f = filter.trim().toLowerCase();
				if (!f) return true;
				return (
					(r.subject_id ?? '').toLowerCase().includes(f) ||
					(r.predicate ?? '').toLowerCase().includes(f) ||
					(r.object_value ?? '').toLowerCase().includes(f)
				);
			})
	);
	let byState = $derived(
		STATES.map((s) => ({
			s,
			rows: rows.filter((r) => r.state === s).sort(byDeadline)
		}))
	);

	let detailOpen = $state(false);
	let detail = $state<(CommitmentRow & { fired: boolean }) | null>(null);
	function openDetail(r: CommitmentRow & { fired: boolean }) {
		detail = r;
		detailOpen = true;
	}
	const fmtv = (v: unknown) => (v == null || v === '' ? '—' : String(v));
</script>

<PageHeader title="Commitment 五态机" subtitle="承诺状态机:created → ACTIVE → 终态;⚠ DUE 与逾期醒目。" />
<div class="mb-4 max-w-xs">
	<Input bind:value={filter} placeholder="筛选 subject / predicate / object…" aria-label="筛选承诺" />
</div>

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
							<li>
								<button
									type="button"
									onclick={() => openDetail(r)}
									class="w-full rounded-control border border-border bg-surface px-3 py-2 text-left text-xs transition hover:border-brand/40"
								>
									<div class="flex items-start justify-between gap-2">
										<span class="font-medium text-fg">{r.subject_id}</span>
										<div class="flex shrink-0 gap-1">
											{#if r.broken_count > 0}<Badge tone="danger">×{r.broken_count}</Badge>{/if}
											{#if r.fired}<Badge tone="warn">⚠ DUE</Badge>{/if}
										</div>
									</div>
									<div class="mt-0.5 text-muted">
										{r.predicate} <span class="text-subtle">→</span> {r.object_value}
									</div>
									{#if r.deadline}
										<div class="mt-1 text-subtle">deadline: {r.deadline}</div>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</Card>
		{/each}
	</div>
{/if}

<Drawer bind:open={detailOpen} title="承诺详情">
	{#if detail}
		<dl class="space-y-2 text-sm">
			{#each Object.entries(detail) as [k, v]}
				<div>
					<dt class="text-xs uppercase tracking-wide text-subtle">{k}</dt>
					<dd class="break-words text-fg">{fmtv(v)}</dd>
				</div>
			{/each}
		</dl>
	{/if}
</Drawer>
