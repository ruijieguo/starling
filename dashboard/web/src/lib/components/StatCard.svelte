<script lang="ts">
	let {
		label,
		value,
		trend = null,
		hint = ''
	}: {
		label: string;
		value: string | number;
		trend?: number | null;
		hint?: string;
	} = $props();
	let tone = $derived(trend === null || trend === 0 ? 'subtle' : trend > 0 ? 'success' : 'danger');
	const toneClass: Record<string, string> = {
		subtle: 'text-subtle',
		success: 'text-success',
		danger: 'text-danger'
	};
</script>

<div class="rounded-xl border border-border bg-card p-4" title={hint}>
	<div class="text-xs uppercase tracking-wide text-muted">{label}</div>
	<div class="mt-1 flex items-baseline gap-2">
		<span class="text-2xl font-semibold text-fg">{value}</span>
		{#if trend !== null && trend !== 0}
			<span class="text-xs {toneClass[tone]}" aria-hidden="true">{trend > 0 ? '↑' : '↓'}{Math.abs(trend)}</span>
		{/if}
	</div>
</div>
