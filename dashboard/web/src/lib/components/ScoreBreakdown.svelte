<script lang="ts">
	// 检索归因:score_breakdown 六因子水平堆叠条(T1,复用于 /interact 逐条 recall 命中展开)。
	// 因子在 C++ 侧(affect_reranker.hpp)已归一到 [0,1](temporal_penalty 是惩罚项,范围 [0,0.3]),
	// 这里按各因子值的相对占比切割堆叠条;segment 与图例均带精确数值 tooltip(title 属性,
	// 与 StatCard 的 hint 惯例一致)。纯前端呈现既有 receipt 数据,不引新视觉体系——配色复用
	// Badge 既有的语义 tone 词汇(brand/info/success/warn/neutral/danger)。
	import type { RecallReceipt } from '$lib/api';

	type ScoreRow = RecallReceipt['score_breakdown'][number];
	type Tone = 'brand' | 'info' | 'success' | 'warn' | 'neutral' | 'danger';
	type FactorKey =
		| 'base'
		| 'recency'
		| 'salience'
		| 'activation'
		| 'affect_consistency'
		| 'temporal_penalty';

	let { row }: { row: ScoreRow } = $props();

	const FACTORS: { key: FactorKey; label: string; tone: Tone }[] = [
		{ key: 'base', label: '基础相关度', tone: 'brand' },
		{ key: 'recency', label: '时近性', tone: 'info' },
		{ key: 'salience', label: '显著性', tone: 'success' },
		{ key: 'activation', label: '激活度', tone: 'warn' },
		{ key: 'affect_consistency', label: '情感一致性', tone: 'neutral' },
		{ key: 'temporal_penalty', label: '时效惩罚', tone: 'danger' }
	];
	const toneBg: Record<Tone, string> = {
		brand: 'bg-brand',
		info: 'bg-info',
		success: 'bg-success',
		warn: 'bg-warn',
		neutral: 'bg-subtle',
		danger: 'bg-danger'
	};

	// 惯例:六因子已在 C++ 侧归一到 [0,1](保底 clamp 防御性负值),这里按相对占比
	// 切分堆叠条的宽度(非公式加权贡献)——纯可视化归因轨迹,不复算 final_score。
	const total = $derived(FACTORS.reduce((sum, f) => sum + Math.max(0, row[f.key]), 0) || 1);
	const segments = $derived(
		FACTORS.map((f) => ({
			...f,
			value: row[f.key],
			pct: (Math.max(0, row[f.key]) / total) * 100
		}))
	);
</script>

<div class="space-y-1.5">
	<div
		class="flex h-2.5 w-full overflow-hidden rounded-full bg-bg"
		role="img"
		aria-label="六因子评分占比"
	>
		{#each segments as s (s.key)}
			{#if s.pct > 0}
				<div
					class="{toneBg[s.tone]} h-full"
					style="width: {s.pct}%"
					title="{s.label}: {s.value.toFixed(3)}"
				></div>
			{/if}
		{/each}
	</div>
	<div class="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-subtle">
		{#each segments as s (s.key)}
			<span class="inline-flex items-center gap-1" title="{s.label}: {s.value.toFixed(3)}">
				<span class="inline-block h-1.5 w-1.5 rounded-full {toneBg[s.tone]}"></span>{s.label}
				<span class="font-mono tabular-nums text-fg">{s.value.toFixed(2)}</span>
			</span>
		{/each}
	</div>
</div>
