<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		title = '',
		children,
		class: klass = ''
	}: { title?: string; children: Snippet; class?: string } = $props();
</script>

<div class="rounded-xl border border-border bg-card p-4 {klass}">
	{#if title}<div class="mb-3 text-sm font-semibold text-fg">{title}</div>{/if}
	{@render children()}
</div>
