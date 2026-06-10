<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Button, EmptyState, Input, Select, Drawer } from '$lib/components/ui';

	let predicate = $state('');
	let perspective = $state('');
	let modality = $state('');
	let polarity = $state('');

	function url() {
		const p = new URLSearchParams();
		if (predicate) p.set('predicate', predicate);
		if (perspective) p.set('perspective', perspective);
		return `/api/statements?${p}`;
	}
	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>(url()));
	$effect(() => {
		q.refetch();
	});

	let allRows = $derived(q.data?.rows ?? []);
	// Facet options derived from the data itself (no hard-coded enum guessing).
	let modalities = $derived([
		'',
		...[...new Set(allRows.map((r) => String(r.modality ?? '')).filter(Boolean))].sort()
	]);
	let polarities = $derived([
		'',
		...[...new Set(allRows.map((r) => String(r.polarity ?? '')).filter(Boolean))].sort()
	]);
	// modality/polarity are client-side facets (server filters predicate/perspective).
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
</script>

<PageHeader title="Statements" subtitle="记忆原子:谁、以何样态与极性、对什么持有判断。" />
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
		<span class="mb-1 block text-xs text-muted">modality</span>
		<Select
			bind:value={modality}
			class="w-40"
			aria-label="modality"
			options={modalities.map((m) => ({ value: m, label: m || '全部' }))}
		/>
	</label>
	<label class="block">
		<span class="mb-1 block text-xs text-muted">polarity</span>
		<Select
			bind:value={polarity}
			class="w-32"
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
		columns={['holder_id', 'holder_perspective', 'subject_id', 'predicate', 'object_value', 'modality', 'polarity']}
	/>
{/if}

<Drawer bind:open={detailOpen} title="Statement 详情">
	{#if detail}
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
