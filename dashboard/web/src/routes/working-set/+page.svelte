<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { toast } from '$lib/ui/toast';
	import { Button, Input, Badge, CopyButton, EmptyState } from '$lib/components/ui';

	let interlocutor = $state('Alice');
	let goal = $state('');
	let budget = $state(2000);
	let ws = $state<{
		render: string;
		blocks: { label: string; content: string; tokens: number }[];
		truncated: string[];
	} | null>(null);
	let busy = $state(false);

	async function load() {
		busy = true;
		try {
			const q = new URLSearchParams({ interlocutor, token_budget: String(budget) });
			if (goal) q.set('goal', goal);
			ws = await api.get(`/api/working_set?${q}`);
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busy = false;
		}
	}
	let totalTokens = $derived((ws?.blocks ?? []).reduce((s, b) => s + b.tokens, 0));
	let pctBudget = $derived(Math.min(100, budget ? (totalTokens / budget) * 100 : 0));
	const SECTION_LABEL: Record<string, string> = {
		persona: '人设 Persona',
		common_ground: '共识 Common Ground',
		relevant_memories: '相关记忆',
		pending_commitments: '待办承诺',
		affect: '情感 Affect'
	};
	const hasDue = (b: { label: string; content: string }) =>
		b.label === 'pending_commitments' && b.content.includes('⚠');
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Working Set</h1>
<div class="mb-3 flex flex-wrap items-end gap-2">
	<Input bind:value={interlocutor} placeholder="interlocutor" class="max-w-40" />
	<Input bind:value={goal} placeholder="goal (optional)" class="max-w-60" />
	<Input type="number" bind:value={budget} placeholder="token budget" class="max-w-32" />
	<Button loading={busy} onclick={load}>渲染</Button>
</div>
{#if ws}
	<div class="space-y-3">
		<div class="flex flex-wrap items-center gap-2">
			<span class="text-xs text-muted">{totalTokens} / {budget} tokens</span>
			<div class="h-2 w-40 overflow-hidden rounded-full bg-surface">
				<div
					class="h-full rounded-full {pctBudget > 90 ? 'bg-warn' : 'bg-brand'}"
					style="width: {pctBudget}%"
				></div>
			</div>
			{#if ws.truncated.length}<Badge tone="warn">truncated: {ws.truncated.join(',')}</Badge>{/if}
			<div class="ml-auto"><CopyButton text={ws.render} label="复制为 prompt" /></div>
		</div>
		{#if ws.blocks.length === 0}
			<EmptyState title="空 working set" description="该 interlocutor / goal 下没有可组装的上下文。" />
		{:else}
			<div class="space-y-2">
				{#each ws.blocks as b}
					<section
						class="rounded-lg border-l-4 bg-card py-2 pl-3 pr-3 {hasDue(b)
							? 'border-l-warn'
							: 'border-l-brand/50'}"
					>
						<div class="mb-1 flex items-center justify-between">
							<span
								class="text-xs font-semibold uppercase tracking-wide {hasDue(b)
									? 'text-warn'
									: 'text-brand'}"
							>
								{SECTION_LABEL[b.label] ?? b.label}
							</span>
							<span class="text-xs text-subtle">{b.tokens} tok</span>
						</div>
						<pre class="whitespace-pre-wrap break-words font-sans text-sm text-fg">{b.content}</pre>
					</section>
				{/each}
			</div>
		{/if}
	</div>
{:else if !busy}
	<EmptyState title="尚未渲染" description="填入 interlocutor 与 goal 后点渲染" />
{/if}
