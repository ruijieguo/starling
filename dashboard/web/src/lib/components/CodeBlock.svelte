<script lang="ts">
	import CopyButton from './ui/CopyButton.svelte';
	let {
		content,
		language = 'text',
		collapsible = false,
		maxHeight = '24rem'
	}: { content: string; language?: 'text' | 'json'; collapsible?: boolean; maxHeight?: string } =
		$props();
	let text = $derived(
		language === 'json'
			? (() => {
					try {
						return JSON.stringify(JSON.parse(content), null, 2);
					} catch {
						return content;
					}
				})()
			: content
	);
	let collapsed = $state(collapsible);
</script>

<div class="rounded-lg border border-border bg-surface">
	<div class="flex items-center justify-between border-b border-border px-3 py-1.5">
		<span class="text-xs text-subtle">{language}</span>
		<div class="flex items-center gap-2">
			{#if collapsible}
				<button class="text-xs text-muted hover:text-fg" onclick={() => (collapsed = !collapsed)}
					>{collapsed ? '展开' : '收起'}</button
				>
			{/if}
			<CopyButton {text} />
		</div>
	</div>
	{#if !collapsed}
		<pre
			class="overflow-auto p-3 text-xs font-mono text-fg"
			style="max-height: {maxHeight}">{text}</pre>
	{/if}
</div>
