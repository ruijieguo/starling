<script lang="ts">
	import { Dialog } from 'bits-ui';
	import Button from './Button.svelte';
	let {
		open = $bindable(false),
		title,
		description = '',
		confirmLabel = '确认',
		cancelLabel = '取消',
		danger = false,
		onconfirm
	}: {
		open?: boolean;
		title: string;
		description?: string;
		confirmLabel?: string;
		cancelLabel?: string;
		danger?: boolean;
		onconfirm: () => void;
	} = $props();
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay class="fixed inset-0 z-50 bg-black/40" />
		<Dialog.Content
			class="fixed left-1/2 top-1/2 z-50 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-5 shadow-lg"
		>
			<Dialog.Title class="text-sm font-semibold text-fg">{title}</Dialog.Title>
			{#if description}
				<Dialog.Description class="mt-1 text-xs text-muted">{description}</Dialog.Description>
			{/if}
			<div class="mt-5 flex justify-end gap-2">
				<Dialog.Close>
					{#snippet child({ props })}
						<Button variant="secondary" {...props}>{cancelLabel}</Button>
					{/snippet}
				</Dialog.Close>
				<Button
					variant={danger ? 'danger' : 'primary'}
					onclick={() => {
						onconfirm();
						open = false;
					}}>{confirmLabel}</Button
				>
			</div>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
