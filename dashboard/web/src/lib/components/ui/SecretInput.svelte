<script lang="ts">
	import Input from './Input.svelte';
	import IconButton from './IconButton.svelte';
	let {
		value = $bindable(''),
		invalid = false,
		placeholder = '',
		id = '',
		class: klass = ''
	}: { value?: string; invalid?: boolean; placeholder?: string; id?: string; class?: string } =
		$props();
	let show = $state(false);
</script>

<div class="flex flex-1 items-center gap-2 {klass}">
	<Input {id} type={show ? 'text' : 'password'} bind:value {invalid} {placeholder} />
	<IconButton
		type="button"
		aria-label={show ? '隐藏密钥' : '显示密钥'}
		aria-pressed={show}
		onclick={() => (show = !show)}
	>
		{#if show}
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
				<path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
				<path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
				<line x1="2" x2="22" y1="2" y2="22" />
			</svg>
		{:else}
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
				<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
				<circle cx="12" cy="12" r="3" />
			</svg>
		{/if}
	</IconButton>
</div>
