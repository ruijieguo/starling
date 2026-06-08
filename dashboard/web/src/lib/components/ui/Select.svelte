<script lang="ts">
	import type { HTMLSelectAttributes } from 'svelte/elements';
	type Opt = { value: string; label: string };
	let {
		value = $bindable(''),
		options,
		class: klass = '',
		...rest
	}: HTMLSelectAttributes & { value?: string; options: Opt[] } = $props();
</script>

<select
	bind:value
	class="w-full rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-fg transition focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand {klass}"
	{...rest}
>
	{#each options as o}<option value={o.value}>{o.label}</option>{/each}
</select>
