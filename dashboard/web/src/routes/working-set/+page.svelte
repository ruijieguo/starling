<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { toast } from '$lib/ui/toast';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import { Button, Input, Badge, CopyButton, EmptyState } from '$lib/components/ui';

	let interlocutor = $state('Alice');
	let goal = $state('');
	let ws = $state<{
		render: string;
		blocks: { label: string; content: string; tokens: number }[];
		truncated: string[];
	} | null>(null);
	let busy = $state(false);

	async function load() {
		busy = true;
		try {
			const q = new URLSearchParams({ interlocutor });
			if (goal) q.set('goal', goal);
			ws = await api.get(`/api/working_set?${q}`);
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busy = false;
		}
	}
	let totalTokens = $derived((ws?.blocks ?? []).reduce((s, b) => s + b.tokens, 0));
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Working Set</h1>
<div class="mb-3 flex gap-2">
	<Input bind:value={interlocutor} placeholder="interlocutor" class="max-w-40" />
	<Input bind:value={goal} placeholder="goal (optional)" class="max-w-60" />
	<Button loading={busy} onclick={load}>渲染</Button>
</div>
{#if ws}
	<div class="space-y-3">
		<div class="flex flex-wrap items-center gap-2">
			{#each ws.blocks as b}<Badge tone="neutral">{b.label} · {b.tokens}</Badge>{/each}
			<span class="text-xs text-muted">共 {totalTokens} tokens</span>
			{#if ws.truncated.length}<Badge tone="warn">truncated: {ws.truncated.join(',')}</Badge>{/if}
			<div class="ml-auto"><CopyButton text={ws.render} label="复制为 prompt" /></div>
		</div>
		<CodeBlock content={ws.render} language="text" />
	</div>
{:else if !busy}
	<EmptyState title="尚未渲染" description="填入 interlocutor 与 goal 后点渲染" />
{/if}
