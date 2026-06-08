<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	let { children, class: klass = '', ...rest }: HTMLButtonAttributes & { children: Snippet } =
		$props();
</script>

<button
	class="inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-surface hover:text-fg transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand {klass}"
	{...rest}
>
	{@render children()}
</button>
