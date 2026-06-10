<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { connectWs } from '$lib/ws';
	import { wsConn, llmConfigured, embedderConfigured, lastWsEvent } from '$lib/health';
	import { StatusDot, IconButton, Toaster, ThemeToggle } from '$lib/components/ui';

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
	const ALL_ITEMS = GROUPS.flatMap((g) => g.items.map((i) => ({ ...i, group: g.title })));

	let { children } = $props();
	let mobileOpen = $state(false);

	const isActive = (href: string) => page.url.pathname === href;
	// 面包屑:Starling › 组 › 页(当前页品牌色)。
	let crumb = $derived(ALL_ITEMS.find((i) => i.href === page.url.pathname));

	// 全局搜索(⌘K):按面板名过滤,Enter/点击跳转。
	let search = $state('');
	let searchFocused = $state(false);
	let searchEl = $state<HTMLInputElement | null>(null);
	let hits = $derived(
		search.trim()
			? ALL_ITEMS.filter((i) => i.label.toLowerCase().includes(search.trim().toLowerCase()))
			: []
	);
	function go(href: string) {
		search = '';
		searchEl?.blur();
		goto(href);
	}
	function onSearchKey(e: KeyboardEvent) {
		if (e.key === 'Enter' && hits.length) go(hits[0].href);
		if (e.key === 'Escape') {
			search = '';
			searchEl?.blur();
		}
	}
	$effect(() => {
		const onKey = (e: KeyboardEvent) => {
			if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
				e.preventDefault();
				searchEl?.focus();
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	// 版本 chip(侧栏底):/health 的 version + 状态点。
	let version = $state('');
	let healthOk = $state<boolean | null>(null);
	$effect(() => {
		api
			.get<{ status: string; version: string }>('/health')
			.then((h) => {
				version = h.version;
				healthOk = h.status === 'ok';
			})
			.catch(() => (healthOk = false));
	});

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

<div class="flex min-h-screen">
	<nav
		class="{mobileOpen
			? 'flex'
			: 'hidden'} w-56 shrink-0 flex-col border-r border-border bg-surface md:flex"
		aria-label="主导航"
	>
		<a href="/" class="flex items-center gap-2.5 px-4 pb-2 pt-4">
			<span class="flex size-8 items-center justify-center rounded-control bg-brand-tint-strong text-base"
				>🪶</span
			>
			<span>
				<span class="block text-[10px] font-semibold uppercase tracking-wider text-subtle"
					>Memory</span
				>
				<span class="block text-sm font-bold leading-tight text-fg">Starling</span>
			</span>
		</a>
		<div class="flex-1 overflow-y-auto px-3 py-2">
			{#each GROUPS as g}
				<div class="mb-4">
					<div class="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-subtle">
						{g.title}
					</div>
					{#each g.items as n}
						<a
							href={n.href}
							aria-current={isActive(n.href) ? 'page' : undefined}
							onclick={() => (mobileOpen = false)}
							class="mb-0.5 block rounded-control px-2.5 py-1.5 text-sm transition {isActive(n.href)
								? 'bg-brand-tint-strong font-medium text-brand'
								: 'text-muted hover:bg-brand-tint hover:text-fg'}">{n.label}</a
						>
					{/each}
				</div>
			{/each}
		</div>
		<div class="border-t border-border px-4 py-3">
			<div
				class="flex items-center justify-between rounded-control border border-border bg-card px-2.5 py-1.5"
			>
				<span class="text-[10px] font-semibold uppercase tracking-wider text-subtle">Version</span>
				<span class="flex items-center gap-1.5 text-xs font-medium text-fg">
					{version || '—'}
					<span
						class="size-1.5 rounded-full {healthOk === true
							? 'bg-success'
							: healthOk === false
								? 'bg-danger'
								: 'bg-subtle'}"
						aria-hidden="true"
					></span>
				</span>
			</div>
		</div>
	</nav>

	<div class="flex min-w-0 flex-1 flex-col">
		<header class="flex items-center gap-3 border-b border-border bg-bg px-5 py-2.5">
			<IconButton class="md:hidden" aria-label="菜单" onclick={() => (mobileOpen = !mobileOpen)}
				>☰</IconButton
			>
			<nav aria-label="面包屑" class="flex items-center gap-1.5 text-sm">
				<a href="/" class="text-subtle hover:text-fg">Starling</a>
				{#if crumb}
					<span class="text-subtle" aria-hidden="true">›</span>
					<span class="text-subtle">{crumb.group}</span>
					<span class="text-subtle" aria-hidden="true">›</span>
					<span class="font-medium text-brand">{crumb.label}</span>
				{/if}
			</nav>
			<div class="relative ml-auto hidden sm:block">
				<input
					bind:this={searchEl}
					bind:value={search}
					onkeydown={onSearchKey}
					onfocus={() => (searchFocused = true)}
					onblur={() => setTimeout(() => (searchFocused = false), 120)}
					placeholder="搜索面板"
					aria-label="搜索面板"
					class="w-44 rounded-full border border-border bg-surface py-1.5 pl-3.5 pr-10 text-sm text-fg placeholder:text-subtle focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand"
				/>
				<kbd
					class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-border bg-card px-1 text-[10px] text-subtle"
					>⌘K</kbd
				>
				{#if searchFocused && hits.length}
					<ul
						class="absolute right-0 top-full z-50 mt-1 w-52 overflow-hidden rounded-control border border-border bg-card py-1 shadow-lg"
					>
						{#each hits as h}
							<li>
								<button
									type="button"
									onmousedown={() => go(h.href)}
									class="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm text-fg hover:bg-brand-tint"
								>
									{h.label}<span class="text-xs text-subtle">{h.group}</span>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>
			<div class="flex items-center gap-3.5">
				<StatusDot tone={connTone} label={connLabel} />
				<StatusDot tone={cfgTone($llmConfigured)} label={$llmConfigured === false ? 'LLM 未配' : 'LLM'} />
				<StatusDot
					tone={cfgTone($embedderConfigured)}
					label={$embedderConfigured === false ? 'Embedder 未配' : 'Embedder'}
				/>
				<ThemeToggle />
			</div>
		</header>

		<main class="flex-1 px-6 py-5">{@render children()}</main>
	</div>
</div>

<Toaster />
