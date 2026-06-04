<script lang="ts">
	let { label, value }: { label: string; value: string | number } = $props();
</script>

<div class="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 bg-white dark:bg-zinc-900">
	<div class="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
	<div class="text-2xl font-semibold mt-1">{value}</div>
</div>
