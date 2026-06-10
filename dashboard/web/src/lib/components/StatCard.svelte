<script lang="ts">
	// KPI 瓷砖(P2.n,参照 OpenClaw Snapshot tile):小型大写标签 + 大数值,
	// 数值可带语义色(tone)与趋势箭头。
	type Tone = 'default' | 'brand' | 'success' | 'warn' | 'danger';
	let {
		label,
		value,
		trend = null,
		hint = '',
		tone = 'default'
	}: {
		label: string;
		value: string | number;
		trend?: number | null;
		hint?: string;
		tone?: Tone;
	} = $props();
	const valueClass: Record<Tone, string> = {
		default: 'text-fg',
		brand: 'text-brand',
		success: 'text-success',
		warn: 'text-warn',
		danger: 'text-danger'
	};
	let trendTone = $derived(trend === null || trend === 0 ? 'subtle' : trend > 0 ? 'success' : 'danger');
	const trendClass: Record<string, string> = {
		subtle: 'text-subtle',
		success: 'text-success',
		danger: 'text-danger'
	};
</script>

<div class="rounded-card border border-border bg-card px-[18px] py-4" title={hint || undefined}>
	<div class="text-[11px] font-semibold uppercase tracking-wider text-subtle">{label}</div>
	<div class="mt-1 flex items-baseline gap-2">
		<span class="text-[28px] font-bold leading-tight {valueClass[tone]}">{value}</span>
		{#if trend !== null && trend !== 0}
			<span class="text-xs {trendClass[trendTone]}" aria-hidden="true">{trend > 0 ? '↑' : '↓'}{Math.abs(trend)}</span>
		{/if}
	</div>
</div>
