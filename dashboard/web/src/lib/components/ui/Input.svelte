<script lang="ts">
	import type { HTMLInputAttributes } from 'svelte/elements';
	let {
		value = $bindable(''),
		invalid = false,
		class: klass = '',
		...rest
	}: HTMLInputAttributes & { invalid?: boolean } = $props();
</script>

<input
	bind:value
	aria-invalid={invalid}
	class="w-full rounded-lg border bg-transparent px-3 py-2 text-sm text-fg placeholder:text-subtle transition focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand {invalid
		? 'border-danger'
		: 'border-border'} {klass}"
	{...rest}
/>
