<script lang="ts">
	import { onMount } from 'svelte';
	import { theme, applyTheme, cycleTheme, type Theme } from '$lib/theme';
	import IconButton from './IconButton.svelte';

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

	const LABEL: Record<Theme, string> = { light: '浅色', dark: '深色', system: '跟随系统' };
	function toggle() {
		const next = cycleTheme(cur);
		theme.set(next);
		applyTheme(next);
	}
</script>

<IconButton aria-label={`主题：${LABEL[cur]}（点击切换）`} title={`主题：${LABEL[cur]}`} onclick={toggle}>
	{#if cur === 'light'}
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41" /></svg>
	{:else if cur === 'dark'}
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" /></svg>
	{:else}
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect width="20" height="14" x="2" y="3" rx="2" /><path d="M8 21h8M12 17v4" /></svg>
	{/if}
</IconButton>
