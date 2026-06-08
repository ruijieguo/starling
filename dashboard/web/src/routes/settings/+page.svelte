<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { llmConfigured, embedderConfigured } from '$lib/health';
	import { getToken, setToken } from '$lib/token';
	import { toast } from '$lib/ui/toast';
	import { missingFields } from '$lib/ui/validate';
	import { Button, Input, Field, Card, CopyButton, ConfirmDialog, SecretInput } from '$lib/components/ui';

	type Prov = { model: string; base_url: string; key_set?: boolean; dim?: number };
	let llm = $state<Prov>({ model: '', base_url: '' });
	let llmKey = $state('');
	let emb = $state<Prov>({ model: '', base_url: '', dim: 1024 });
	let embKey = $state('');
	let saving = $state(false);
	let errors = $state<Record<string, boolean>>({});
	let confirmOpen = $state(false);
	let embBaseline = $state('');

	let token = $state(getToken());

	$effect(() => {
		api
			.get<{ llm: Prov; embedder: Prov }>('/api/config')
			.then((c) => {
				llm = c.llm;
				emb = c.embedder;
				embBaseline = JSON.stringify({ m: c.embedder.model, b: c.embedder.base_url, d: c.embedder.dim });
			})
			.catch((e) => toast.error(String((e as ApiError).message)));
	});

	let embChanged = $derived(
		embBaseline !== JSON.stringify({ m: emb.model, b: emb.base_url, d: emb.dim }) || !!embKey
	);

	function validate(): boolean {
		const miss = [
			...missingFields(llm, { keyRequired: true, keySet: !!llm.key_set, keyInput: llmKey }).map(
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
				llm: { model: llm.model, base_url: llm.base_url, ...(llmKey ? { api_key: llmKey } : {}) },
				embedder: {
					model: emb.model,
					base_url: emb.base_url,
					dim: emb.dim,
					...(embKey ? { api_key: embKey } : {})
				}
			};
			const c = await api.post<{ llm: Prov; embedder: Prov }>('/api/config', payload);
			llm = c.llm;
			emb = c.embedder;
			llmKey = '';
			embKey = '';
			embBaseline = JSON.stringify({ m: c.embedder.model, b: c.embedder.base_url, d: c.embedder.dim });
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
			<Field label="model" for="llm-model" error={errors['llm.model'] ? 'model 必填' : ''}>
				<Input id="llm-model" bind:value={llm.model} invalid={errors['llm.model']} placeholder="如 gpt-4o-mini" />
			</Field>
			<Field label="base_url" for="llm-base" hint="留空用默认 OpenAI 端点">
				<Input id="llm-base" bind:value={llm.base_url} placeholder="https://api.openai.com/v1" />
			</Field>
			<Field label="api_key" for="llm-key" error={errors['llm.api_key'] ? 'api_key 必填' : ''}>
				<SecretInput id="llm-key" bind:value={llmKey} invalid={errors['llm.api_key']} placeholder={llm.key_set ? '已设置 · 留空不改' : 'api_key'} />
			</Field>
		</div>
	</Card>

	<Card title="Embedder（召回用）">
		<div class="space-y-3">
			<Field label="model" for="emb-model">
				<Input id="emb-model" bind:value={emb.model} placeholder="如 text-embedding-3-small" />
			</Field>
			<Field label="base_url" for="emb-base" hint="留空用默认端点">
				<Input id="emb-base" bind:value={emb.base_url} placeholder="https://api.openai.com/v1" />
			</Field>
			<Field label="dim" for="emb-dim" hint="改 dim 会按新配置重嵌已有记忆">
				<Input id="emb-dim" type="number" bind:value={emb.dim} />
			</Field>
			<Field label="api_key" for="emb-key" hint="留空则用离线 stub(召回不可用)">
				<SecretInput id="emb-key" bind:value={embKey} placeholder={emb.key_set ? '已设置 · 留空不改' : 'api_key（可空）'} />
			</Field>
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
