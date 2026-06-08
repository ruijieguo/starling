<script lang="ts">
	import type { Snippet } from 'svelte';
	type Tone = 'neutral' | 'brand' | 'success' | 'warn' | 'danger' | 'info';
	let { tone = 'neutral', children }: { tone?: Tone; children: Snippet } = $props();
	const tones: Record<Tone, string> = {
		neutral: 'border-border text-muted',
		brand: 'border-brand/30 text-brand',
		success: 'border-success/30 text-success',
		warn: 'border-warn/30 text-warn',
		danger: 'border-danger/30 text-danger',
		info: 'border-info/30 text-info'
	};
</script>

<span
	class="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium {tones[tone]}"
	>{@render children()}</span
>
