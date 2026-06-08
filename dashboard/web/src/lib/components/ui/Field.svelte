<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		label,
		hint = '',
		error = '',
		for: htmlFor = '',
		children
	}: { label: string; hint?: string; error?: string; for?: string; children: Snippet } = $props();
</script>

<div class="space-y-1">
	<label class="block text-xs font-medium text-muted" for={htmlFor}>{label}</label>
	{@render children()}
	{#if error}
		<p class="text-xs text-danger">{error}</p>
	{:else if hint}
		<p class="text-xs text-subtle">{hint}</p>
	{/if}
</div>
