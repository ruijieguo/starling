<script lang="ts">
	import { onMount } from 'svelte';
	import { theme, applyTheme, type Theme } from '$lib/theme';

	let cur = $state<Theme>('system');
	const unsub = theme.subscribe((t) => (cur = t));

	onMount(() => {
		applyTheme(cur);
		const mq = matchMedia('(prefers-color-scheme: dark)');
		const onChange = () => {
			if (cur === 'system') applyTheme('system');
		};
		mq.addEventListener('change', onChange);
		return () => {
			mq.removeEventListener('change', onChange);
			unsub();
		};
	});

	// P2.n:循环单钮 → 三态分段簇(跟随系统/浅色/深色),当前态 tint 高亮。
	const MODES: { value: Theme; label: string }[] = [
		{ value: 'system', label: '跟随系统' },
		{ value: 'light', label: '浅色' },
		{ value: 'dark', label: '深色' }
	];
	function pick(t: Theme) {
		theme.set(t);
		applyTheme(t);
	}
</script>

<div
	class="flex items-center gap-0.5 rounded-full border border-border bg-surface p-0.5"
	role="group"
	aria-label="主题"
>
	{#each MODES as m}
		<button
			type="button"
			aria-label={`主题：${m.label}`}
			title={m.label}
			aria-pressed={cur === m.value}
			onclick={() => pick(m.value)}
			class="flex size-7 items-center justify-center rounded-full transition focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand {cur === m.value
				? 'bg-brand-tint-strong text-brand'
				: 'text-subtle hover:text-fg'}"
		>
			{#if m.value === 'light'}
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" /></svg>
			{:else if m.value === 'dark'}
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" /></svg>
			{:else}
				<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="14" x="2" y="3" rx="2" /><path d="M8 21h8M12 17v4" /></svg>
			{/if}
		</button>
	{/each}
</div>
