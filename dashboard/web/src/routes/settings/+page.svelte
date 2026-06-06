<script lang="ts">
	import { api } from '$lib/api';
	type Prov = { model: string; base_url: string; key_set?: boolean; dim?: number };
	let llm = $state<Prov>({ model: '', base_url: '' });
	let llmKey = $state('');
	let emb = $state<Prov>({ model: '', base_url: '', dim: 1024 });
	let embKey = $state('');
	let msg = $state('');
	$effect(() => {
		api.get<{ llm: Prov; embedder: Prov }>('/api/config')
			.then((c) => { llm = c.llm; emb = c.embedder; }).catch((e) => (msg = String(e)));
	});
	async function save() {
		try {
			const payload: Record<string, unknown> = {
				llm: { model: llm.model, base_url: llm.base_url, ...(llmKey ? { api_key: llmKey } : {}) },
				embedder: { model: emb.model, base_url: emb.base_url, dim: emb.dim,
					...(embKey ? { api_key: embKey } : {}) }
			};
			const c = await api.post<{ llm: Prov; embedder: Prov }>('/api/config', payload);
			llm = c.llm; emb = c.embedder; llmKey = ''; embKey = ''; msg = '已保存';
		} catch (e) { msg = String(e); }
	}
</script>
<h1 class="text-xl font-semibold mb-4">设置</h1>
<div class="space-y-6 max-w-xl">
	<section class="space-y-2">
		<h2 class="text-sm font-semibold text-zinc-500">LLM（抽取用）{#if llm.key_set}<span class="text-green-600 text-xs"> · 已配置</span>{/if}</h2>
		<input bind:value={llm.model} placeholder="model（如 gpt-4o-mini）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={llm.base_url} placeholder="base_url（可选）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={llmKey} type="password" placeholder={llm.key_set ? 'api_key（留空不改）' : 'api_key'} class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
	</section>
	<section class="space-y-2">
		<h2 class="text-sm font-semibold text-zinc-500">Embedder（召回用）{#if emb.key_set}<span class="text-green-600 text-xs"> · 已配置</span>{/if}</h2>
		<input bind:value={emb.model} placeholder="model（如 text-embedding-v3）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={emb.base_url} placeholder="base_url（可选）" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={emb.dim} type="number" placeholder="dim" class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<input bind:value={embKey} type="password" placeholder={emb.key_set ? 'api_key（留空不改）' : 'api_key'} class="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent p-2 text-sm" />
		<p class="text-xs text-zinc-400">改 embedder 会重嵌已有记忆（dim 变化）。</p>
	</section>
	<button onclick={save} class="px-3 py-1.5 rounded-lg bg-zinc-900 text-white dark:bg-white dark:text-zinc-900 text-sm">保存</button>
	<span class="text-xs text-zinc-500 ml-2">{msg}</span>
</div>
