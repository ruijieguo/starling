<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
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

<h1 class="mb-4 text-xl font-semibold text-fg">Statements</h1>
<div class="mb-3 flex flex-wrap gap-2">
	<Input bind:value={predicate} placeholder="predicate" class="max-w-40" />
	<Input bind:value={perspective} placeholder="perspective" class="max-w-40" />
	<Button variant="secondary" onclick={() => q.refetch()}>筛选</Button>
	<Select
		bind:value={modality}
		class="max-w-44"
		aria-label="modality"
		options={modalities.map((m) => ({ value: m, label: m || '全部 modality' }))}
	/>
	<Select
		bind:value={polarity}
		class="max-w-36"
		aria-label="polarity"
		options={polarities.map((p) => ({ value: p, label: p || '全部 polarity' }))}
	/>
</div>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else}
	<p class="mb-2 text-xs text-subtle">{rows.length} 条 · 点击行看详情</p>
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
