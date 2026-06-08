<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
	let {
		variant = 'primary',
		loading = false,
		children,
		class: klass = '',
		disabled,
		...rest
	}: HTMLButtonAttributes & { variant?: Variant; loading?: boolean; children: Snippet } = $props();
	const styles: Record<Variant, string> = {
		primary: 'bg-brand text-brand-fg hover:opacity-90',
		secondary: 'border border-border bg-card hover:bg-surface text-fg',
		ghost: 'hover:bg-surface text-fg',
		danger: 'bg-danger text-white hover:opacity-90'
	};
</script>

<button
	class="inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand {styles[variant]} {klass}"
	disabled={disabled || loading}
	{...rest}
>
	{#if loading}<span class="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>{/if}
	{@render children()}
</button>
