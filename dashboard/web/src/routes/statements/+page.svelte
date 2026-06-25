<script lang="ts">
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import { toast } from '$lib/ui/toast';
	import DataTable from '$lib/components/DataTable.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Button, EmptyState, Input, Select, Drawer, ConfirmDialog } from '$lib/components/ui';

	let predicate = $state('');
	let perspective = $state('');
	let reviewStatus = $state(''); // 服务端过滤(片 6:='review_requested' 即审批队列)
	let modality = $state('');
	let polarity = $state('');

	function url() {
		const p = new URLSearchParams();
		if (predicate) p.set('predicate', predicate);
		if (perspective) p.set('perspective', perspective);
		if (reviewStatus) p.set('review_status', reviewStatus);
		return `/api/statements?${p}`;
	}
	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>(url()));
	$effect(() => {
		reviewStatus; // dep:改服务端审批过滤即重取(predicate/perspective 仍走「筛选」按钮)
		q.refetch();
	});

	let allRows = $derived(q.data?.rows ?? []);
	let modalities = $derived([
		'',
		...[...new Set(allRows.map((r) => String(r.modality ?? '')).filter(Boolean))].sort()
	]);
	let polarities = $derived([
		'',
		...[...new Set(allRows.map((r) => String(r.polarity ?? '')).filter(Boolean))].sort()
	]);
	let rows = $derived(
		allRows.filter(
			(r) => (!modality || r.modality === modality) && (!polarity || r.polarity === polarity)
		)
	);

	let detailOpen = $state(false);
	let detail = $state<Record<string, unknown> | null>(null);
	function openDetail(r: Record<string, unknown>) {
		detail = r;
		detailOpen = true;
	}
	const fmtv = (v: unknown) => (v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v));

	// ── 片 6 干预动作(全经唯一写者漏斗;成功后关抽屉 + 重取) ─────────────
	let busy = $state(false);
	let confirmOpen = $state(false);
	let confirmCfg = $state<{ title: string; desc: string; run: () => Promise<void> } | null>(null);

	async function act(label: string, fn: () => Promise<unknown>) {
		busy = true;
		try {
			await fn();
			toast.success(`${label}成功`);
			detailOpen = false;
			await q.refetch();
		} catch (e) {
			toast.error(`${label}失败:${e instanceof Error ? e.message : String(e)}`);
		} finally {
			busy = false;
		}
	}
	const approve = (id: string) => act('批准', () => api.post('/api/review', { stmt_id: id }));
	const reconsolidate = (id: string) =>
		act('请求再固化', () => api.post('/api/reconsolidate', { stmt_id: id }));
	function askForget(id: string, reject: boolean) {
		confirmCfg = {
			title: reject ? '拒绝并遗忘此语句?' : '遗忘此语句?',
			desc: '逻辑删除(→ forgotten,移出检索与回放池)。不可逆。',
			run: () => act(reject ? '拒绝' : '遗忘', () => api.post('/api/forget', { ids: [id] }))
		};
		confirmOpen = true;
	}
</script>

<PageHeader title="语句" subtitle="记忆原子 Statement:谁、以何样态与极性、对什么持有判断。" />
<div class="mb-4 flex flex-wrap items-end gap-3">
	<label class="block">
		<span class="mb-1 block text-xs text-muted">predicate</span>
		<Input bind:value={predicate} placeholder="如 responsible_for" class="w-44" />
	</label>
	<label class="block">
		<span class="mb-1 block text-xs text-muted">perspective</span>
		<Input bind:value={perspective} placeholder="如 first_person" class="w-44" />
	</label>
	<label class="block">
		<span class="mb-1 block text-xs text-muted">review_status</span>
		<Select
			bind:value={reviewStatus}
			class="w-36"
			aria-label="review_status"
			options={[
				{ value: '', label: '全部' },
				{ value: 'review_requested', label: '待审批' },
				{ value: 'approved', label: '已批准' },
				{ value: 'pending_review', label: '待复核' },
				{ value: 'rejected', label: '已拒绝' }
			]}
		/>
	</label>
	<label class="block">
		<span class="mb-1 block text-xs text-muted">modality</span>
		<Select
			bind:value={modality}
			class="w-32"
			aria-label="modality"
			options={modalities.map((m) => ({ value: m, label: m || '全部' }))}
		/>
	</label>
	<label class="block">
		<span class="mb-1 block text-xs text-muted">polarity</span>
		<Select
			bind:value={polarity}
			class="w-28"
			aria-label="polarity"
			options={polarities.map((p) => ({ value: p, label: p || '全部' }))}
		/>
	</label>
	<Button variant="soft" onclick={() => q.refetch()}>筛选</Button>
	<span class="ml-auto pb-1.5 text-xs text-subtle">{rows.length} 条 · 点击行看详情</span>
</div>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else}
	<DataTable
		{rows}
		loading={q.loading}
		emptyText="无 statements"
		onRowClick={openDetail}
		columns={['subject_id', 'predicate', 'object_value', 'modality', 'consolidation_state', 'review_status']}
	/>
{/if}

<Drawer bind:open={detailOpen} title="Statement 详情">
	{#if detail}
		{@const sid = String(detail.id ?? '')}
		{@const rs = String(detail.review_status ?? '')}
		{@const cs = String(detail.consolidation_state ?? '')}
		{#if sid}
			<div class="mb-3 flex flex-wrap gap-2">
				<Button variant="soft" onclick={() => goto(`/lens?stmt=${encodeURIComponent(sid)}`)}>
					透视来源 →
				</Button>
				{#if rs === 'review_requested'}
					<Button variant="soft" disabled={busy} onclick={() => approve(sid)}>批准</Button>
					<Button variant="danger" disabled={busy} onclick={() => askForget(sid, true)}>拒绝</Button>
				{/if}
				{#if cs === 'consolidated'}
					<Button variant="soft" disabled={busy} onclick={() => reconsolidate(sid)}>请求再固化</Button>
				{/if}
				<Button variant="ghost" disabled={busy} onclick={() => askForget(sid, false)}>遗忘</Button>
			</div>
		{/if}
		<dl class="space-y-2 text-sm">
			{#each Object.entries(detail) as [k, v]}
				<div>
					<dt class="text-xs uppercase tracking-wide text-subtle">{k}</dt>
					{#if v !== null && typeof v === 'object'}
						<CodeBlock content={JSON.stringify(v)} language="json" />
					{:else}
						<dd class="break-words text-fg">{fmtv(v)}</dd>
					{/if}
				</div>
			{/each}
		</dl>
	{/if}
</Drawer>

<ConfirmDialog
	bind:open={confirmOpen}
	title={confirmCfg?.title ?? ''}
	description={confirmCfg?.desc ?? ''}
	confirmLabel="确认"
	danger
	onconfirm={() => confirmCfg?.run()}
/>
