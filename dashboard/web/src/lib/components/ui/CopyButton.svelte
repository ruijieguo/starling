<script lang="ts">
	let { text, label = '复制' }: { text: string; label?: string } = $props();
	let copied = $state(false);
	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			copied = false;
		}
	}
</script>

<button
	onclick={copy}
	class="inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md border border-border px-2 py-1 text-xs text-muted hover:text-fg transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
	>{copied ? '已复制' : label}</button
>
