<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { llmConfigured, embedderConfigured } from '$lib/health';
	import { getToken, setToken } from '$lib/token';
	import { toast } from '$lib/ui/toast';
	import { missingFields } from '$lib/ui/validate';
	import { CHAT_PROVIDERS, EMBED_PROVIDERS, chatPreset, embedPreset } from '$lib/providers';
	import {
		Button, Input, Field, Card, CopyButton, ConfirmDialog, SecretInput, Select, StatusDot
	} from '$lib/components/ui';

	type Prov = { provider?: string; model: string; base_url: string; key_set?: boolean; dim?: number };
	type TestResult = { ok: boolean; detail: string; ms: number };

	let llm = $state<Prov>({ provider: 'openai', model: '', base_url: '' });
	let llmKey = $state('');
	let emb = $state<Prov>({ provider: 'openai', model: '', base_url: '', dim: 1024 });
	let embKey = $state('');
	let saving = $state(false);
	let errors = $state<Record<string, boolean>>({});
	let confirmOpen = $state(false);
	let embBaseline = $state('');
	let token = $state(getToken());

	let llmTest = $state<TestResult | null>(null);
	let embTest = $state<TestResult | null>(null);
	let testingLlm = $state(false);
	let testingEmb = $state(false);

	const provOpts = (list: { id: string; label: string }[]) =>
		list.map((p) => ({ value: p.id, label: p.label }));

	$effect(() => {
		api
			.get<{ llm: Prov; embedder: Prov }>('/api/config')
			.then((c) => {
				llm = { provider: 'openai', ...c.llm };
				emb = { provider: 'openai', ...c.embedder };
				embBaseline = JSON.stringify({ p: emb.provider, m: emb.model, b: emb.base_url, d: emb.dim });
			})
			.catch((e) => toast.error(String((e as ApiError).message)));
	});

	let embChanged = $derived(
		embBaseline !== JSON.stringify({ p: emb.provider, m: emb.model, b: emb.base_url, d: emb.dim }) ||
			!!embKey
	);
	let llmPreset = $derived(chatPreset(llm.provider));
	let embPresetCur = $derived(embedPreset(emb.provider));
	// No key (and none typed) → embedder silently falls back to the offline stub.
	let embDegraded = $derived(!emb.key_set && !embKey);

	function applyLlmPreset() {
		const p = chatPreset(llm.provider);
		if (p) {
			if (p.base_url) llm.base_url = p.base_url;
			if (!llm.model && p.models.length) llm.model = p.models[0];
		}
		llmTest = null;
	}
	function applyEmbPreset() {
		const p = embedPreset(emb.provider);
		if (p) {
			if (p.base_url) emb.base_url = p.base_url;
			if (!emb.model && p.models.length) emb.model = p.models[0];
		}
		embTest = null;
	}

	async function testLlm() {
		testingLlm = true;
		llmTest = null;
		try {
			const r = await api.post<{ ok: boolean; detail: string; latency_ms: number }>(
				'/api/config/test',
				{ kind: 'llm', provider: llm.provider, model: llm.model, base_url: llm.base_url, ...(llmKey ? { api_key: llmKey } : {}) }
			);
			llmTest = { ok: r.ok, detail: r.detail, ms: r.latency_ms };
		} catch (e) {
			llmTest = { ok: false, detail: String((e as ApiError).message), ms: 0 };
		} finally {
			testingLlm = false;
		}
	}
	async function testEmb() {
		testingEmb = true;
		embTest = null;
		try {
			const r = await api.post<{ ok: boolean; detail: string; latency_ms: number }>(
				'/api/config/test',
				{ kind: 'embedder', provider: emb.provider, model: emb.model, base_url: emb.base_url, dim: emb.dim, ...(embKey ? { api_key: embKey } : {}) }
			);
			embTest = { ok: r.ok, detail: r.detail, ms: r.latency_ms };
		} catch (e) {
			embTest = { ok: false, detail: String((e as ApiError).message), ms: 0 };
		} finally {
			testingEmb = false;
		}
	}

	function validate(): boolean {
		const llmNeedsKey = !!chatPreset(llm.provider)?.needs_key;
		const miss = [
			...missingFields(llm, { keyRequired: llmNeedsKey, keySet: !!llm.key_set, keyInput: llmKey }).map(
				(f) => `llm.${f}`
			),
			...missingFields(emb, { keyRequired: false, keySet: !!emb.key_set, keyInput: embKey }).map(
				(f) => `emb.${f}`
			)
		];
		errors = Object.fromEntries(miss.map((k) => [k, true]));
		return miss.length === 0;
	}

	function onSaveClick() {
		if (!validate()) {
			toast.error('请补全必填字段');
			return;
		}
		if (embChanged) confirmOpen = true;
		else void doSave();
	}

	async function doSave() {
		saving = true;
		try {
			const payload = {
				llm: { provider: llm.provider, model: llm.model, base_url: llm.base_url, ...(llmKey ? { api_key: llmKey } : {}) },
				embedder: { provider: emb.provider, model: emb.model, base_url: emb.base_url, dim: emb.dim, ...(embKey ? { api_key: embKey } : {}) }
			};
			const c = await api.post<{ llm: Prov; embedder: Prov }>('/api/config', payload);
			llm = { provider: 'openai', ...c.llm };
			emb = { provider: 'openai', ...c.embedder };
			llmKey = '';
			embKey = '';
			embBaseline = JSON.stringify({ p: emb.provider, m: emb.model, b: emb.base_url, d: emb.dim });
			llmConfigured.set(c.llm.key_set ?? null);
			embedderConfigured.set(c.embedder.key_set ?? null);
			toast.success('已保存');
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			saving = false;
		}
	}

	function saveToken() {
		setToken(token);
		toast.success('Token 已更新');
	}
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">设置</h1>
<div class="max-w-xl space-y-5">
	<Card title="LLM（抽取用）">
		<div class="space-y-3">
			<Field label="provider" for="llm-provider" hint="预设会自动填 base_url 与常用模型">
				<Select id="llm-provider" bind:value={llm.provider} options={provOpts(CHAT_PROVIDERS)} onchange={applyLlmPreset} />
			</Field>
			<Field label="model" for="llm-model" error={errors['llm.model'] ? 'model 必填' : ''}>
				<Input id="llm-model" bind:value={llm.model} invalid={errors['llm.model']} list="llm-models" placeholder="如 gpt-4o-mini" />
				<datalist id="llm-models">{#each llmPreset?.models ?? [] as m}<option value={m}></option>{/each}</datalist>
			</Field>
			<Field label="base_url" for="llm-base" hint="留空用 provider 默认端点">
				<Input id="llm-base" bind:value={llm.base_url} placeholder="https://api.openai.com/v1" />
			</Field>
			<Field
				label="api_key"
				for="llm-key"
				error={errors['llm.api_key'] ? 'api_key 必填' : ''}
				hint={llmPreset && !llmPreset.needs_key ? '本地 provider，可留空' : ''}
			>
				<SecretInput id="llm-key" bind:value={llmKey} invalid={errors['llm.api_key']} placeholder={llm.key_set ? '已设置 · 留空不改' : 'api_key'} />
			</Field>
			<div class="flex flex-wrap items-center gap-3">
				<Button variant="secondary" loading={testingLlm} onclick={testLlm}>测试连接</Button>
				{#if llmTest}
					<StatusDot tone={llmTest.ok ? 'ok' : 'down'} label={llmTest.ok ? `连通 · ${llmTest.ms}ms` : `失败: ${llmTest.detail}`} />
				{/if}
			</div>
		</div>
	</Card>

	<Card title="Embedder（召回用）">
		<div class="space-y-3">
			<Field label="provider" for="emb-provider" hint="Anthropic 无 embedding API；用 OpenAI/Voyage/本地">
				<Select id="emb-provider" bind:value={emb.provider} options={provOpts(EMBED_PROVIDERS)} onchange={applyEmbPreset} />
			</Field>
			<Field label="model" for="emb-model">
				<Input id="emb-model" bind:value={emb.model} list="emb-models" placeholder="如 text-embedding-3-small" />
				<datalist id="emb-models">{#each embPresetCur?.models ?? [] as m}<option value={m}></option>{/each}</datalist>
			</Field>
			<Field label="base_url" for="emb-base" hint="留空用 provider 默认端点">
				<Input id="emb-base" bind:value={emb.base_url} placeholder="https://api.openai.com/v1" />
			</Field>
			<Field label="dim" for="emb-dim" hint="改 dim 会按新配置重嵌已有记忆">
				<Input id="emb-dim" type="number" bind:value={emb.dim} />
			</Field>
			<Field label="api_key" for="emb-key" hint="留空则用离线 stub（召回不可用）">
				<SecretInput id="emb-key" bind:value={embKey} placeholder={emb.key_set ? '已设置 · 留空不改' : 'api_key（可空）'} />
			</Field>
			<div class="flex flex-wrap items-center gap-3">
				<Button variant="secondary" loading={testingEmb} onclick={testEmb}>测试连接</Button>
				{#if embTest}
					<StatusDot tone={embTest.ok ? 'ok' : 'down'} label={embTest.ok ? `连通 · ${embTest.detail}` : `失败: ${embTest.detail}`} />
				{/if}
				{#if embDegraded}
					<StatusDot tone="warn" label="未启用（stub）· 召回不可用" />
				{/if}
			</div>
		</div>
	</Card>

	<Button loading={saving} onclick={onSaveClick}>保存</Button>

	<Card title="Access">
		<div class="space-y-3">
			<Field label="API Token" for="tok" hint="粘贴 #token=… 登录 URL，或在此直接输入">
				<div class="flex gap-2">
					<SecretInput id="tok" bind:value={token} placeholder="bearer token" />
					<CopyButton text={token} />
				</div>
			</Field>
			<Button variant="secondary" onclick={saveToken}>保存 Token</Button>
		</div>
	</Card>
</div>

<ConfirmDialog
	bind:open={confirmOpen}
	title="确认更改 Embedder？"
	description="改 embedder 配置会按新设置重嵌已有记忆，可能耗时。继续？"
	confirmLabel="继续保存"
	onconfirm={doSave}
/>
