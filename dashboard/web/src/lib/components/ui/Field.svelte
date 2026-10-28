<script lang="ts">
	import type { Snippet } from 'svelte';
	// 控件由调用方经 children 渲染,Field 没法从内部给它加属性;改为把关联信息作为 snippet
	// 参数交给调用方透传到控件上:
	//   describedBy —— 实际渲染出来的提示/错误元素的 id(由 for 派生;都没渲染时为 undefined);
	//   invalid     —— 有错误时为 true,对应控件的 aria-invalid。
	// 不需要的调用方照旧写隐式 children,参数被忽略。
	let {
		label,
		hint = '',
		error = '',
		for: htmlFor = '',
		children
	}: {
		label: string;
		hint?: string;
		error?: string;
		for?: string;
		children: Snippet<[{ describedBy: string | undefined; invalid: boolean }]>;
	} = $props();

	let hintId = $derived(htmlFor ? `${htmlFor}-hint` : undefined);
	let errorId = $derived(htmlFor ? `${htmlFor}-error` : undefined);
	// 有错误时错误替换提示,只列出实际渲染的那一个。
	let describedBy = $derived(error ? errorId : hint ? hintId : undefined);
</script>

<div class="space-y-1">
	<label class="block text-xs font-medium text-muted" for={htmlFor}>{label}</label>
	{@render children({ describedBy, invalid: !!error })}
	{#if error}
		<p id={errorId} class="text-xs text-danger">{error}</p>
	{:else if hint}
		<p id={hintId} class="text-xs text-subtle">{hint}</p>
	{/if}
</div>
