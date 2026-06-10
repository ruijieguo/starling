<script lang="ts">
	// 页头(P2.n):品牌色标题 + 一句话副题,12 面板统一使用。
	import type { Snippet } from 'svelte';
	let {
		title,
		subtitle = '',
		actions
	}: { title: string; subtitle?: string; actions?: Snippet } = $props();
</script>

<div class="mb-5 flex items-end justify-between gap-3">
	<div>
		<h1 class="text-2xl font-bold text-brand">{title}</h1>
		{#if subtitle}<p class="mt-0.5 text-sm text-muted">{subtitle}</p>{/if}
	</div>
	{#if actions}<div class="flex shrink-0 items-center gap-2">{@render actions()}</div>{/if}
</div>
