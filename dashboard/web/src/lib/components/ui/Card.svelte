<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		title = '',
		description = '',
		actions,
		children,
		class: klass = ''
	}: {
		title?: string;
		description?: string;
		actions?: Snippet;
		children: Snippet;
		class?: string;
	} = $props();
</script>

<div class="rounded-card border border-border bg-card p-[18px] {klass}">
	{#if title || actions}
		<div class="mb-3 flex items-start justify-between gap-3">
			<div>
				{#if title}<div class="text-sm font-semibold text-fg">{title}</div>{/if}
				{#if description}<div class="mt-0.5 text-xs text-subtle">{description}</div>{/if}
			</div>
			{#if actions}<div class="flex shrink-0 items-center gap-2">{@render actions()}</div>{/if}
		</div>
	{/if}
	{@render children()}
</div>
