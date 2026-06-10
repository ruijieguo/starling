<script lang="ts">
	// Pill 标签(P2.n,参照 OpenClaw 实例标签组):列表行内的小型元数据 chip。
	import type { Snippet } from 'svelte';
	let { children, class: klass = '' }: { children: Snippet; class?: string } = $props();
</script>

<span
	class="inline-flex items-center rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs text-muted {klass}"
	>{@render children()}</span
>
