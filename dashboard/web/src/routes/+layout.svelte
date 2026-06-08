<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { connectWs } from '$lib/ws';
	import { wsConn, llmConfigured, embedderConfigured, lastWsEvent } from '$lib/health';
	import { StatusDot, IconButton, Toaster } from '$lib/components/ui';

	const GROUPS = [
		{
			title: '观测',
			items: [
				{ href: '/', label: '总览' },
				{ href: '/statements', label: 'Statements' },
				{ href: '/cognizers', label: 'Cognizers' },
				{ href: '/commitments', label: 'Commitments' }
			]
		},
		{
			title: '交互',
			items: [
				{ href: '/interact', label: '交互' },
				{ href: '/working-set', label: 'Working Set' },
				{ href: '/reminders', label: '承诺提醒' }
			]
		},
		{
			title: '诊断',
			items: [
				{ href: '/queues', label: 'Queues' },
				{ href: '/conflicts', label: 'Conflicts' },
				{ href: '/replay', label: 'Replay' },
				{ href: '/eval', label: 'Eval' }
			]
		},
		{ title: '设置', items: [{ href: '/settings', label: '设置' }] }
	];

	let { children } = $props();
	let mobileOpen = $state(false);

	const isActive = (href: string) => page.url.pathname === href;

	$effect(() => {
		const dispose = connectWs((e) => lastWsEvent.set(e));
		return dispose;
	});
	$effect(() => {
		api
			.get<{ llm: { key_set: boolean }; embedder: { key_set: boolean } }>('/api/config')
			.then((c) => {
				llmConfigured.set(c.llm.key_set ?? null);
				embedderConfigured.set(c.embedder.key_set ?? null);
			})
			.catch(() => {
				llmConfigured.set(null);
				embedderConfigured.set(null);
			});
	});

	let connTone = $derived(
		($wsConn === 'open' ? 'ok' : $wsConn === 'connecting' ? 'warn' : 'down') as 'ok' | 'warn' | 'down'
	);
	let connLabel = $derived($wsConn === 'open' ? 'Live' : $wsConn === 'connecting' ? '连接中' : '断开');
	const cfgTone = (v: boolean | null) => (v === true ? 'ok' : v === false ? 'warn' : 'unknown');
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="flex min-h-screen flex-col">
	<header class="flex h-12 items-center gap-3 border-b border-border px-4">
		<IconButton class="md:hidden" aria-label="菜单" onclick={() => (mobileOpen = !mobileOpen)}>☰</IconButton>
		<a href="/" class="font-semibold text-fg">Starling</a>
		<span class="text-xs text-subtle">self · 记忆体</span>
		<div class="ml-auto flex items-center gap-4">
			<StatusDot tone={connTone} label={connLabel} />
			<StatusDot tone={cfgTone($llmConfigured)} label={$llmConfigured === false ? 'LLM 未配' : 'LLM'} />
			<StatusDot tone={cfgTone($embedderConfigured)} label={$embedderConfigured === false ? 'Embedder 未配' : 'Embedder'} />
		</div>
	</header>

	<div class="flex flex-1">
		<nav
			class="{mobileOpen ? 'block' : 'hidden'} w-52 shrink-0 border-r border-border p-3 md:block"
			aria-label="主导航"
		>
			{#each GROUPS as g}
				<div class="mb-4">
					<div class="px-2 pb-1 text-xs font-semibold uppercase tracking-wide text-subtle">{g.title}</div>
					{#each g.items as n}
						<a
							href={n.href}
							aria-current={isActive(n.href) ? 'page' : undefined}
							onclick={() => (mobileOpen = false)}
							class="block rounded-lg px-2 py-1.5 text-sm transition {isActive(n.href)
								? 'bg-brand/10 font-medium text-brand'
								: 'text-muted hover:bg-surface hover:text-fg'}">{n.label}</a
						>
					{/each}
				</div>
			{/each}
		</nav>

		<main class="flex-1 p-6">{@render children()}</main>
	</div>
</div>

<Toaster />
