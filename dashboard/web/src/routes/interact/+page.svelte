<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { toast } from '$lib/ui/toast';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Button, Textarea, Input, Badge, Card, Select } from '$lib/components/ui';

	let text = $state('');
	let holder = $state('');
	let interlocutor = $state('');
	let query = $state('');
	let mode = $state('semantic');
	let remembered = $state<string[]>([]);
	let outcome = $state('');
	let results = $state<{ subject: string; predicate: string; object: string; score: number }[]>([]);
	let recalled = $state(false);
	let busyR = $state(false);
	let busyQ = $state(false);

	async function remember() {
		busyR = true;
		try {
			const body: Record<string, unknown> = { text };
			if (holder) body.holder = holder;
			if (interlocutor) body.interlocutor = interlocutor;
			// 真模型抽取实测 20-110s(长文本更慢),放宽到 180s(后端有自己的重试与超时)。
			const r = await api.post<{ statement_ids: string[]; outcome: string }>('/api/remember', body, {
				timeoutMs: 180_000
			});
			remembered = r.statement_ids;
			outcome = r.outcome;
			toast.success(`outcome: ${r.outcome} · ${r.statement_ids.length} statements`);
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busyR = false;
		}
	}
	async function recall() {
		busyQ = true;
		try {
			const r = await api.post<{ results: typeof results }>(
				'/api/recall',
				{ query, mode },
				{ timeoutMs: 60_000 } // query embed 走网络,留足重试余量
			);
			results = r.results;
			recalled = true;
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busyQ = false;
		}
	}
	const pct = (s: number) => Math.max(2, Math.min(100, s * 100));
</script>

<PageHeader title="交互" subtitle="控制台:remember 写入与 recall 检索。" />
<div class="max-w-2xl space-y-4">
	<Card title="Remember" description="自然语言写入,抽取为 statements。">
		<div class="space-y-2">
			<Textarea bind:value={text} rows={3} placeholder="记一段话…" />
			<div class="flex flex-wrap gap-2">
				<Input bind:value={holder} placeholder="holder (默认 self)" class="max-w-44" />
				<Input bind:value={interlocutor} placeholder="interlocutor (可选)" class="max-w-44" />
			</div>
			<div class="flex items-center gap-3">
				<Button variant="soft" loading={busyR} disabled={!text.trim()} onclick={remember}>记住</Button>
				{#if remembered.length || outcome}
					<span class="text-xs text-muted">{outcome} · {remembered.length} statements</span>
				{/if}
			</div>
			{#if remembered.length}
				<div class="flex flex-wrap gap-1">
					{#each remembered as id}
						<a href="/statements" title={id}><Badge tone="brand">{id.slice(0, 8)}…</Badge></a>
					{/each}
				</div>
			{/if}
		</div>
	</Card>
	<Card title="Recall" description="语义检索或模式补全,按相似度打分。">
		<div class="space-y-3">
			<div class="flex flex-wrap gap-2">
				<Input bind:value={query} placeholder="query" class="min-w-48 flex-1" />
				<Select
					bind:value={mode}
					class="max-w-40"
					aria-label="recall 模式"
					options={[
						{ value: 'semantic', label: '语义检索' },
						{ value: 'completion', label: '模式补全' }
					]}
				/>
				<Button loading={busyQ} disabled={!query.trim()} variant="soft" onclick={recall}>
					检索
				</Button>
			</div>
			{#if recalled}
				{#if results.length === 0}
					<p class="text-sm text-muted">无召回结果</p>
				{:else}
					<ul class="space-y-2">
						{#each results as r}
							<li class="rounded-control border border-border bg-surface px-3 py-2">
								<div class="flex items-center justify-between gap-2">
									<span class="text-sm text-fg">
										{r.subject} <span class="text-subtle">{r.predicate}</span> {r.object}
									</span>
									<span class="shrink-0 text-xs tabular-nums text-muted">{r.score.toFixed(3)}</span>
								</div>
								<div class="mt-1 h-1.5 overflow-hidden rounded-full bg-bg">
									<div class="h-full rounded-full bg-brand" style="width: {pct(r.score)}%"></div>
								</div>
							</li>
						{/each}
					</ul>
				{/if}
			{/if}
		</div>
	</Card>
</div>
