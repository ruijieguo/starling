<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import { getToken, setToken } from '$lib/token';

	let token = $state(getToken());
	const NAV = [
		{ href: '/', label: '总览' },
		{ href: '/eval', label: 'Eval' },
		{ href: '/interact', label: '交互' },
		{ href: '/working-set', label: 'Working Set' },
		{ href: '/reminders', label: '承诺提醒' },
		{ href: '/statements', label: 'Statements' },
		{ href: '/cognizers', label: 'Cognizers' },
		{ href: '/commitments', label: 'Commitments' },
		{ href: '/replay', label: 'Replay' },
		{ href: '/conflicts', label: 'Conflicts' },
		{ href: '/queues', label: 'Queues' }
	];
	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="flex min-h-screen">
	<nav class="w-48 shrink-0 border-r border-zinc-200 dark:border-zinc-800 p-3 space-y-1">
		<div class="font-semibold px-2 py-3">Starling</div>
		{#each NAV as n}
			<a
				href={n.href}
				class="block px-2 py-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-sm"
				>{n.label}</a
			>
		{/each}
		<div class="pt-4 px-2">
			<label class="text-xs text-zinc-500" for="tok">Token</label>
			<input
				id="tok"
				class="w-full mt-1 px-2 py-1 text-xs rounded border border-zinc-300 dark:border-zinc-700 bg-transparent"
				bind:value={token}
				onchange={() => setToken(token)}
				placeholder="bearer token"
			/>
		</div>
	</nav>
	<main class="flex-1 p-6">{@render children()}</main>
</div>
