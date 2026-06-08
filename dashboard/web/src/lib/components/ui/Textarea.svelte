<script lang="ts">
	import type { HTMLTextareaAttributes } from 'svelte/elements';
	let { value = $bindable(''), class: klass = '', ...rest }: HTMLTextareaAttributes = $props();
</script>

<textarea
	bind:value
	class="w-full rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-fg placeholder:text-subtle transition focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand {klass}"
	{...rest}
></textarea>
