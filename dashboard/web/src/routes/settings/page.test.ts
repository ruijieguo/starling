import { describe, it, expect, vi, beforeEach } from 'vitest';
import { tick } from 'svelte';
import { render, fireEvent } from '@testing-library/svelte';

// /api/config 是这页唯一的外部依赖。get 决定加载成败;post 是我们要证明「没被调用」的那个。
const get = vi.fn();
const post = vi.fn();
vi.mock('$lib/api', () => ({
	api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), del: vi.fn() },
	ApiError: class ApiError extends Error {}
}));

import Settings from './+page.svelte';

const byText = (c: HTMLElement | HTMLBodyElement, t: string) =>
	[...c.querySelectorAll('button')].find((b) => b.textContent?.trim() === t) as
		| HTMLButtonElement
		| undefined;

const saveButton = (c: HTMLElement) => byText(c, '保存');

// 顺序有讲究:先 tick() 让挂载后的 $effect 真正跑起来(它才发出 api.get),再 flush
// 微任务让 promise 落地,最后一次 tick() 把状态变更刷进 DOM。先 flush 再 tick 是不行的
// —— 那时请求还没发出去。
const settle = async () => {
	await tick();
	await Promise.resolve();
	await Promise.resolve();
	await tick();
};

// embedding 绑定的 provider 必须带 dim:dim 那个 <Input> 是 bind:value 且有 '' fallback,
// undefined 会让 Svelte 5 抛 props_invalid_value(源码里那条 $effect 正是为此兜底的,
// 但它赶不在首次渲染之前)。这是既有行为,与本文件要测的加载门无关,故在 fixture 里避开。
const CONFIG = {
	providers: { p1: { provider: 'openai', model: 'm', base_url: 'http://x', dim: 1024 } },
	roles: { extraction: 'p1', embedding: 'p1', chat: 'p1' },
	gist_thresholds: { min_holders: 5 }
};

describe('设置页:配置加载门(数据丢失防线)', () => {
	beforeEach(() => {
		get.mockReset();
		post.mockReset();
	});

	// 这是本文件存在的理由。加载失败后页面各项是空的,若此时能保存,提交的就是从未加载过的
	// 初值:providers {} 对后端是 no-op(upsert)所以 key 安全,但 roles 走赋值 ——
	// {extraction:'',embedding:'',chat:''} 会解绑全部角色,后端随即热切换 set_llm({}) /
	// rebuild_embedder({}),抽取与嵌入当场停摆;gist_thresholds 送 {} 则重置为默认。
	// 最后 cfg.save() 写进 starling.json。整条链只能由一次 POST 触发,所以钉住「不 POST」。
	it('加载失败后点保存,绝不 POST /api/config', async () => {
		get.mockRejectedValue(new Error('401 unauthorized'));
		const { container } = render(Settings);
		await settle();

		const btn = saveButton(container);
		expect(btn, '保存按钮应当存在').toBeTruthy();
		expect(btn!.disabled, '加载失败时保存按钮必须禁用').toBe(true);

		await fireEvent.click(btn!);
		await settle();
		expect(post).not.toHaveBeenCalled();
	});

	// 两道防线必须分开测。上面那条只覆盖按钮的 disabled —— 实测证明:把 doSave 里的
	// 函数级守卫删掉、只留 disabled,本文件依然全绿,因为 fireEvent.click 对 disabled
	// 按钮根本不派发事件,守卫压根没被执行过。这里手动摘掉 disabled 再点,模拟「日后
	// 多出一条绕过按钮的调用路径」,让守卫本身也有独立断言力。
	it('函数级守卫:即便绕过按钮的 disabled 触发保存,也不 POST', async () => {
		get.mockRejectedValue(new Error('401 unauthorized'));
		const { container } = render(Settings);
		await settle();

		const btn = saveButton(container)!;
		expect(btn.disabled).toBe(true);
		btn.disabled = false; // 绕过第一道防线
		await fireEvent.click(btn);
		await settle();

		// 未加载时 embBaseline('') 必然 !== embKey(),故 onSaveClick 走的是「先弹确认框」
		// 那条分支 —— doSave 只在确认之后才被调用。不点完这一步,守卫根本没被触达
		// (这正是本条测试第一版假绿的原因)。真实的数据丢失路径也正是这条:
		// 用户点保存 → 看到一个莫名其妙的「确认更改 Embedder?」→ 点继续。
		// ConfirmDialog 走 bits-ui 的 Dialog.Portal,渲染在 document.body 而非 container 里。
		const confirm = byText(document.body, '继续保存');
		expect(confirm, '应当弹出确认框(未加载时 embChanged 恒为真)').toBeTruthy();
		await fireEvent.click(confirm!);
		await settle();
		expect(post, 'doSave 的 !loaded 守卫应当拦住它').not.toHaveBeenCalled();
	});

	it('加载失败时显示原因,并说明空态不等于「没配」', async () => {
		get.mockRejectedValue(new Error('401 unauthorized'));
		const { container } = render(Settings);
		await settle();

		const text = container.textContent ?? '';
		expect(text).toContain('配置加载失败');
		expect(text, '必须带上失败原因,而不是笼统一句失败').toContain('401 unauthorized');
		expect(text, '必须解释下方为空的原因,否则用户会读成「什么都没配」').toContain('不是真的没配');
	});

	it('Access 卡片在加载失败时仍然可见 —— 它是 token 出错时的唯一自救途径', async () => {
		get.mockRejectedValue(new Error('401 unauthorized'));
		const { container } = render(Settings);
		await settle();
		expect(container.textContent ?? '').toContain('Access');
	});

	it('加载成功后保存按钮可用,且 POST 得出去', async () => {
		get.mockResolvedValue(CONFIG);
		post.mockResolvedValue(CONFIG);
		const { container } = render(Settings);
		await settle();

		const btn = saveButton(container);
		expect(btn!.disabled, '加载成功后不该再禁用').toBe(false);
		await fireEvent.click(btn!);
		await settle();
		expect(post).toHaveBeenCalled();
		expect(post.mock.calls[0][0]).toBe('/api/config');
	});

	it('重试成功后解除封锁(一次失败不该永久锁死这页)', async () => {
		get.mockRejectedValueOnce(new Error('boom')).mockResolvedValue(CONFIG);
		const { container } = render(Settings);
		await settle();
		expect(saveButton(container)!.disabled).toBe(true);

		const retry = [...container.querySelectorAll('button')].find(
			(b) => b.textContent?.trim() === '重试'
		);
		expect(retry, '加载失败时应当给一个重试按钮').toBeTruthy();
		await fireEvent.click(retry!);
		await settle();
		expect(saveButton(container)!.disabled, '重试成功后应解除禁用').toBe(false);
	});
});
