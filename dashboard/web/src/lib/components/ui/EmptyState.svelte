<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		title,
		description = '',
		children
	}: { title: string; description?: string; children?: Snippet } = $props();
</script>

<div class="rounded-xl border border-dashed border-border p-8 text-center">
	<p class="text-sm font-medium text-fg">{title}</p>
	{#if description}<p class="mt-1 text-xs text-subtle">{description}</p>{/if}
	{#if children}<div class="mt-3">{@render children()}</div>{/if}
</div>
