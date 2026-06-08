<script lang="ts">
	type Tone = 'ok' | 'warn' | 'down' | 'unknown';
	let { tone = 'unknown', label }: { tone?: Tone; label: string } = $props();
	const tones: Record<Tone, string> = {
		ok: 'bg-success',
		warn: 'bg-warn',
		down: 'bg-danger',
		unknown: 'bg-subtle'
	};
</script>

<span class="inline-flex items-center gap-1.5 text-xs text-muted">
	<span class="size-2 rounded-full {tones[tone]}" aria-hidden="true"></span>{label}
</span>
