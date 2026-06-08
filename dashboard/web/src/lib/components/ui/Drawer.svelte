<script lang="ts">
	import { Dialog } from 'bits-ui';
	import type { Snippet } from 'svelte';
	let {
		open = $bindable(false),
		title = '',
		children
	}: { open?: boolean; title?: string; children: Snippet } = $props();
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay class="fixed inset-0 z-50 bg-black/40" />
		<Dialog.Content
			class="fixed right-0 top-0 z-50 flex h-full w-[92vw] max-w-md flex-col overflow-y-auto border-l border-border bg-card p-5 shadow-lg"
		>
			<div class="mb-3 flex items-center justify-between gap-2">
				<Dialog.Title class="text-sm font-semibold text-fg">{title}</Dialog.Title>
				<Dialog.Close class="rounded-md px-2 py-1 text-sm text-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">✕</Dialog.Close>
			</div>
			{@render children()}
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
