<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { byDeadline, deriveFired } from '$lib/commitments';
	import { createQuery } from '$lib/query.svelte';
	import { toast } from '$lib/ui/toast';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Badge, Card, EmptyState, Skeleton, Input, Drawer, Button, ConfirmDialog } from '$lib/components/ui';

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

	// #39 片6 手动流转(仅对 ACTIVE 有效):fulfill=标记完成;withdraw=撤回(释放保护,需确认)。
	// 核心 ACTIVE 守卫,非 ACTIVE → 路由 409 → 提示并刷新(可能已被后台 tick 改状态)。
	// 全经单写者命令漏斗(POST /api/commitment/*),成功后重取刷新看板。
	let busy = $state(false);
	let confirmOpen = $state(false);
	let confirmCfg = $state<{ title: string; desc: string; run: () => Promise<void> } | null>(null);

	async function transition(stmtId: string, kind: 'fulfill' | 'withdraw') {
		busy = true;
		try {
			await api.post(`/api/commitment/${kind}`, { stmt_id: stmtId });
			toast.success(kind === 'fulfill' ? '已标记完成' : '已撤回');
			detailOpen = false;
			await q.refetch();
		} catch (e) {
			if (e instanceof ApiError && e.status === 409) {
				// 409 同时覆盖「已非 ACTIVE(后台 tick 改了状态)」与「该承诺不存在」两种 no-op。
				toast.error('无法流转:该承诺已非 ACTIVE 或不存在(可能已被后台 tick 改变);已刷新');
				detailOpen = false;
				await q.refetch();
			} else {
				toast.error(`流转失败:${e instanceof Error ? e.message : String(e)}`);
			}
		} finally {
			busy = false;
		}
	}

	function askWithdraw(stmtId: string) {
		confirmCfg = {
			title: '撤回此承诺?',
			desc: '承诺 → WITHDRAWN 并释放保护:它保护的记忆此后按正常衰减、可能被遗忘。仅对 ACTIVE 有效,不可逆。',
			run: () => transition(stmtId, 'withdraw')
		};
		confirmOpen = true;
	}
</script>

<PageHeader title="承诺状态机" subtitle="Commitment:created → ACTIVE → 终态;⚠ DUE 与逾期醒目。" />
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
		{#if detail.state === 'ACTIVE'}
			<div class="mt-4 flex gap-2 border-t border-border pt-4">
				<Button variant="soft" disabled={busy} onclick={() => transition(detail!.stmt_id, 'fulfill')}>
					标记完成
				</Button>
				<Button variant="danger" disabled={busy} onclick={() => askWithdraw(detail!.stmt_id)}>
					撤回
				</Button>
			</div>
			<p class="mt-2 text-xs text-subtle">
				手动流转仅对 ACTIVE 承诺有效;fire / break / auto-withdraw 由后台 tick 自动处理。
			</p>
		{/if}
	{/if}
</Drawer>

<ConfirmDialog
	bind:open={confirmOpen}
	title={confirmCfg?.title ?? ''}
	description={confirmCfg?.desc ?? ''}
	onconfirm={() => confirmCfg?.run()}
/>
