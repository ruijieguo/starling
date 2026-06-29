# P2.k Dashboard 地基 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 dashboard 前端从"裸 zinc 线框图"升级为有品味、一致、有完整状态反馈的产品地基——设计系统 token + 组件库 + 新壳/IA 重组 + 数据层加固 + 全 12 面板套壳统一态。

**Architecture:** 纯前端(`dashboard/web`,Svelte 5 runes / SvelteKit / Tailwind v4)。Tailwind v4 用 `@theme` 定义语义 token(slate 中性 + indigo 品牌 + 语义色,明暗随 OS 偏好等价);新建 `src/lib/components/ui/` 组件库(手写基础件 + bits-ui Dialog + svelte-sonner Toast);新建 `createQuery` 数据原语统一 载入/空/错;`+layout.svelte` 换成分组侧栏 + 当前页高亮 + 三盏健康灯;12 个 `+page.svelte` 保留各自 fetch 逻辑、只换壳与状态件。零 C++、零 migration、不改后端 API。

**Tech Stack:** Svelte 5.55(runes)· SvelteKit 2.57(adapter-static)· Tailwind v4.3(`@tailwindcss/vite`)· Vite 8 · TypeScript 6 · vitest 4.1(jsdom + `@testing-library/svelte`)· Playwright 1.60 · 新增 `bits-ui` · `svelte-sonner` · `@fontsource-variable/inter` · `@fontsource-variable/jetbrains-mono`。

**全局约束(每个 Task 适用):**
- 工作目录 `dashboard/web`;运行命令前 `cd` 到该目录。所有改动文件都在 `dashboard/web/` 下,不碰仓库其余部分(与并行 p2-c C++ 任务零重叠)。
- `git add` 只用 **explicit path**(`git add dashboard/web/<file>`),绝不 `git add .`/`-A`。无 `--no-verify`/`--amend`。不推 main。
- 本 plan 文件保留 untracked 直到 P2.k 收尾。
- 设计系统:克制现代(slate + indigo,明暗随 OS 等价);**颜色不作唯一信号**(健康/状态都配文字或图标)。每个异步视图都要有 载入 / 空 / 错 三态。
- 本期**不**做单面板深度信息重构(P2.m),**不**碰多 provider 后端 / 测连通(P2.l)。设置页本期仍是单一 OpenAI 兼容字段,但 UX 质变(show/hide、校验、save toast、重嵌确认弹窗)。
- 验收:`npx vitest run` 绿 + `npx playwright test` 绿 + `npm run check`(svelte-check)零错 + `npm run build` 绿。

---

### Task 0: Worktree + 基线

**Files:**
- 无源码改动(环境准备 + 基线记录)

- [ ] **Step 1: 建 worktree(从最新 main 切,隔离并行任务)**

REQUIRED SUB-SKILL: superpowers:using-git-worktrees。从 main HEAD 建 `worktree-p2-k-dashboard-foundation`(分支 `p2-k-dashboard-foundation`)。

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling
git fetch origin && git worktree add -b p2-k-dashboard-foundation .claude/worktrees/p2-k-dashboard-foundation origin/main
cd .claude/worktrees/p2-k-dashboard-foundation/dashboard/web
```
Expected: worktree 创建成功,落在 `dashboard/web`。

- [ ] **Step 2: 装依赖 + 跑基线**

Run:
```bash
npm install
npx vitest run
npx playwright test
npm run check
```
Expected: `npm install` 成功;vitest 基线(`token.test.ts` 3 + `api.test.ts` 2 = 5 passed);playwright 基线(`smoke.spec.ts` 1 passed,如缺浏览器先 `npx playwright install`);`svelte-check` 0 errors。**记录这些基线数**,后续每个 Task 不得令其回退(只增不减)。

- [ ] **Step 3: 记录基线到 commit(空改动不提交,仅口头记录)**

无需 commit。把基线写进 Task 进度笔记:vitest 5 passed / playwright 1 passed / svelte-check clean / build ok。

---

### Task 1: 设计 token + 字体 + 依赖

**Files:**
- Modify: `dashboard/web/src/app.css`(现 3 行 → token 体系)
- Modify: `dashboard/web/package.json`(加依赖)
- Create: `dashboard/web/src/lib/ui/density.ts`(密度类型 + 帮助)
- Test: `dashboard/web/src/lib/ui/density.test.ts`

- [ ] **Step 1: 装依赖**

Run:
```bash
npm install bits-ui svelte-sonner @fontsource-variable/inter @fontsource-variable/jetbrains-mono
```
Expected: 四个包入 `package.json` dependencies(注意:它们是运行时依赖,会进 `dependencies` 非 `devDependencies`,符合预期)。`npm run build` 仍绿。
> 若 `bits-ui` / `svelte-sonner` 安装后 `npm run check` 报 Svelte 5 兼容问题,用 `npx ctx7@latest library "bits-ui" "Svelte 5 Dialog component"` 与 `... "svelte-sonner" "Svelte 5 Toaster"` 查当前 API 版本并对齐(本 plan 按 bits-ui v1 / svelte-sonner v1 的 API 写;若版本不同,以 ctx7 文档为准微调组件包装,接口名不变)。

- [ ] **Step 2: 写密度帮助 + 失败测试**

Create `dashboard/web/src/lib/ui/density.ts`:
```ts
export type Density = 'comfortable' | 'compact';

/** Rows-per-page default per density (used by DataTable). */
export const pageSizeFor = (d: Density): number => (d === 'compact' ? 25 : 12);
```

Create `dashboard/web/src/lib/ui/density.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { pageSizeFor } from './density';

describe('pageSizeFor', () => {
	it('compact is denser than comfortable', () => {
		expect(pageSizeFor('compact')).toBeGreaterThan(pageSizeFor('comfortable'));
	});
});
```

- [ ] **Step 3: 跑测试,确认失败**

Run: `npx vitest run src/lib/ui/density.test.ts`
Expected: FAIL(`density.ts` 刚建应能解析;若先建好则 PASS——本步主要确保文件被 vitest 纳入。若 PASS 直接进下一步)。

- [ ] **Step 4: 重写 `app.css` 为 token 体系**

替换 `dashboard/web/src/app.css` 全文:
```css
@import 'tailwindcss';
@import '@fontsource-variable/inter';
@import '@fontsource-variable/jetbrains-mono';

/* 语义 token → Tailwind 工具类(@theme inline:工具类在使用点解析变量,
   故下面的明暗/媒体查询覆盖会被工具类自动跟随)。 */
@theme inline {
	--color-bg: var(--bg);
	--color-surface: var(--surface);
	--color-card: var(--card);
	--color-fg: var(--fg);
	--color-muted: var(--muted);
	--color-subtle: var(--subtle);
	--color-border: var(--border);
	--color-brand: var(--brand);
	--color-brand-fg: var(--brand-fg);
	--color-success: var(--success);
	--color-warn: var(--warn);
	--color-danger: var(--danger);
	--color-info: var(--info);
	--font-sans: 'Inter Variable', ui-sans-serif, system-ui, sans-serif;
	--font-mono: 'JetBrains Mono Variable', ui-monospace, monospace;
	--radius-card: 0.75rem;
}

/* 浅色(默认) */
:root {
	--bg: #fafafa;
	--surface: #ffffff;
	--card: #ffffff;
	--fg: #18181b;
	--muted: #52525b;
	--subtle: #71717a;
	--border: #e4e4e7;
	--brand: #4f46e5;
	--brand-fg: #ffffff;
	--success: #16a34a;
	--warn: #d97706;
	--danger: #dc2626;
	--info: #2563eb;
	/* 密度:DataTable 行垂直内边距 */
	--row-py: 0.5rem;
}

/* 深色随 OS 偏好(明暗等价,无手动开关——开关留 P2.m) */
@media (prefers-color-scheme: dark) {
	:root {
		--bg: #09090b;
		--surface: #0c0c0f;
		--card: #18181b;
		--fg: #fafafa;
		--muted: #a1a1aa;
		--subtle: #71717a;
		--border: #27272a;
		--brand: #6366f1;
		--brand-fg: #ffffff;
		--success: #22c55e;
		--warn: #f59e0b;
		--danger: #ef4444;
		--info: #3b82f6;
	}
}

/* 密度模式:容器上 data-density="compact" 收紧表格行 */
[data-density='compact'] {
	--row-py: 0.25rem;
}

:root {
	color-scheme: light dark;
}
body {
	background: var(--bg);
	color: var(--fg);
	font-family: var(--font-sans);
}
```

- [ ] **Step 5: 跑校验**

Run: `npx vitest run src/lib/ui/density.test.ts && npm run check && npm run build`
Expected: vitest PASS;svelte-check 0 errors;build 绿(字体 + token 被打包)。

- [ ] **Step 6: Commit**

```bash
git add dashboard/web/src/app.css dashboard/web/src/lib/ui/density.ts dashboard/web/src/lib/ui/density.test.ts dashboard/web/package.json dashboard/web/package-lock.json
git commit -F - <<'EOF'
feat(P2.k/dash): 设计 token 体系 + 字体 + 依赖

app.css 从 3 行裸 zinc 扩成语义 token(@theme inline 映射 Tailwind 工具类:
bg/surface/card/fg/muted/subtle/border/brand/success/warn/danger/info),
明暗随 prefers-color-scheme 等价(手动开关留 P2.m);Inter + JetBrains Mono
变量字体本地打包(@fontsource-variable);密度模式 data-density=compact
收紧 --row-py。引入 bits-ui(Dialog)+ svelte-sonner(Toast)。

EOF
```

---

### Task 2: 基础展示组件(手写)

**Files:**
- Create: `dashboard/web/src/lib/components/ui/Button.svelte`
- Create: `dashboard/web/src/lib/components/ui/IconButton.svelte`
- Create: `dashboard/web/src/lib/components/ui/Input.svelte`
- Create: `dashboard/web/src/lib/components/ui/Textarea.svelte`
- Create: `dashboard/web/src/lib/components/ui/Field.svelte`
- Create: `dashboard/web/src/lib/components/ui/Card.svelte`
- Create: `dashboard/web/src/lib/components/ui/Badge.svelte`
- Create: `dashboard/web/src/lib/components/ui/StatusDot.svelte`
- Create: `dashboard/web/src/lib/components/ui/Skeleton.svelte`
- Create: `dashboard/web/src/lib/components/ui/EmptyState.svelte`
- Create: `dashboard/web/src/lib/components/ui/CopyButton.svelte`
- Create: `dashboard/web/src/lib/components/ui/index.ts`
- Test: `dashboard/web/src/lib/components/ui/ui.test.ts`

- [ ] **Step 1: Button**

Create `dashboard/web/src/lib/components/ui/Button.svelte`:
```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
	let {
		variant = 'primary',
		loading = false,
		children,
		class: klass = '',
		disabled,
		...rest
	}: HTMLButtonAttributes & { variant?: Variant; loading?: boolean; children: Snippet } = $props();
	const styles: Record<Variant, string> = {
		primary: 'bg-brand text-brand-fg hover:opacity-90',
		secondary: 'border border-border bg-card hover:bg-surface text-fg',
		ghost: 'hover:bg-surface text-fg',
		danger: 'bg-danger text-white hover:opacity-90'
	};
</script>

<button
	class="inline-flex items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand {styles[variant]} {klass}"
	disabled={disabled || loading}
	{...rest}
>
	{#if loading}<span class="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>{/if}
	{@render children()}
</button>
```

- [ ] **Step 2: IconButton**

Create `dashboard/web/src/lib/components/ui/IconButton.svelte`:
```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	let { children, class: klass = '', ...rest }: HTMLButtonAttributes & { children: Snippet } =
		$props();
</script>

<button
	class="inline-flex size-8 items-center justify-center rounded-lg text-muted hover:bg-surface hover:text-fg transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand {klass}"
	{...rest}
>
	{@render children()}
</button>
```

- [ ] **Step 3: Input + Textarea**

Create `dashboard/web/src/lib/components/ui/Input.svelte`:
```svelte
<script lang="ts">
	import type { HTMLInputAttributes } from 'svelte/elements';
	let {
		value = $bindable(''),
		invalid = false,
		class: klass = '',
		...rest
	}: HTMLInputAttributes & { invalid?: boolean } = $props();
</script>

<input
	bind:value
	aria-invalid={invalid}
	class="w-full rounded-lg border bg-transparent px-3 py-2 text-sm text-fg placeholder:text-subtle transition focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand {invalid
		? 'border-danger'
		: 'border-border'} {klass}"
	{...rest}
/>
```

Create `dashboard/web/src/lib/components/ui/Textarea.svelte`:
```svelte
<script lang="ts">
	import type { HTMLTextareaAttributes } from 'svelte/elements';
	let { value = $bindable(''), class: klass = '', ...rest }: HTMLTextareaAttributes = $props();
</script>

<textarea
	bind:value
	class="w-full rounded-lg border border-border bg-transparent px-3 py-2 text-sm text-fg placeholder:text-subtle transition focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-brand {klass}"
	{...rest}
></textarea>
```

- [ ] **Step 4: Field(label + hint + error 包裹)**

Create `dashboard/web/src/lib/components/ui/Field.svelte`:
```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		label,
		hint = '',
		error = '',
		for: htmlFor = '',
		children
	}: { label: string; hint?: string; error?: string; for?: string; children: Snippet } = $props();
</script>

<div class="space-y-1">
	<label class="block text-xs font-medium text-muted" for={htmlFor}>{label}</label>
	{@render children()}
	{#if error}
		<p class="text-xs text-danger">{error}</p>
	{:else if hint}
		<p class="text-xs text-subtle">{hint}</p>
	{/if}
</div>
```

- [ ] **Step 5: Card + Badge + StatusDot**

Create `dashboard/web/src/lib/components/ui/Card.svelte`:
```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		title = '',
		children,
		class: klass = ''
	}: { title?: string; children: Snippet; class?: string } = $props();
</script>

<div class="rounded-xl border border-border bg-card p-4 {klass}">
	{#if title}<div class="mb-3 text-sm font-semibold text-fg">{title}</div>{/if}
	{@render children()}
</div>
```

Create `dashboard/web/src/lib/components/ui/Badge.svelte`:
```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	type Tone = 'neutral' | 'brand' | 'success' | 'warn' | 'danger' | 'info';
	let { tone = 'neutral', children }: { tone?: Tone; children: Snippet } = $props();
	const tones: Record<Tone, string> = {
		neutral: 'border-border text-muted',
		brand: 'border-brand/30 text-brand',
		success: 'border-success/30 text-success',
		warn: 'border-warn/30 text-warn',
		danger: 'border-danger/30 text-danger',
		info: 'border-info/30 text-info'
	};
</script>

<span
	class="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium {tones[tone]}"
	>{@render children()}</span
>
```

Create `dashboard/web/src/lib/components/ui/StatusDot.svelte`(颜色 + 文字,颜色非唯一信号):
```svelte
<script lang="ts">
	type Tone = 'ok' | 'warn' | 'down' | 'unknown';
	let { tone = 'unknown', label }: { tone?: Tone; label: string } = $props();
	const tones: Record<Tone, string> = {
		ok: 'bg-success',
		warn: 'bg-warn',
		down: 'bg-danger',
		unknown: 'bg-subtle'
	};
</script>

<span class="inline-flex items-center gap-1.5 text-xs text-muted">
	<span class="size-2 rounded-full {tones[tone]}" aria-hidden="true"></span>{label}
</span>
```

- [ ] **Step 6: Skeleton + EmptyState**

Create `dashboard/web/src/lib/components/ui/Skeleton.svelte`:
```svelte
<script lang="ts">
	let { class: klass = 'h-4 w-full' }: { class?: string } = $props();
</script>

<div class="animate-pulse rounded-md bg-border/60 {klass}" aria-hidden="true"></div>
```

Create `dashboard/web/src/lib/components/ui/EmptyState.svelte`:
```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		title,
		description = '',
		children
	}: { title: string; description?: string; children?: Snippet } = $props();
</script>

<div class="rounded-xl border border-dashed border-border p-8 text-center">
	<p class="text-sm font-medium text-fg">{title}</p>
	{#if description}<p class="mt-1 text-xs text-subtle">{description}</p>{/if}
	{#if children}<div class="mt-3">{@render children()}</div>{/if}
</div>
```

- [ ] **Step 7: CopyButton**

Create `dashboard/web/src/lib/components/ui/CopyButton.svelte`:
```svelte
<script lang="ts">
	let { text, label = '复制' }: { text: string; label?: string } = $props();
	let copied = $state(false);
	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
			copied = true;
			setTimeout(() => (copied = false), 1500);
		} catch {
			copied = false;
		}
	}
</script>

<button
	onclick={copy}
	class="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted hover:text-fg transition"
	>{copied ? '已复制' : label}</button
>
```

- [ ] **Step 8: 桶导出 index.ts**

Create `dashboard/web/src/lib/components/ui/index.ts`:
```ts
export { default as Button } from './Button.svelte';
export { default as IconButton } from './IconButton.svelte';
export { default as Input } from './Input.svelte';
export { default as Textarea } from './Textarea.svelte';
export { default as Field } from './Field.svelte';
export { default as Card } from './Card.svelte';
export { default as Badge } from './Badge.svelte';
export { default as StatusDot } from './StatusDot.svelte';
export { default as Skeleton } from './Skeleton.svelte';
export { default as EmptyState } from './EmptyState.svelte';
export { default as CopyButton } from './CopyButton.svelte';
```

- [ ] **Step 9: 渲染冒烟测试**

Create `dashboard/web/src/lib/components/ui/ui.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import Button from './Button.svelte';
import EmptyState from './EmptyState.svelte';
import StatusDot from './StatusDot.svelte';

describe('ui components', () => {
	it('Button renders its label and disables when loading', () => {
		const { getByRole } = render(Button, {
			props: { loading: true, children: (() => 'Save') as never }
		});
		expect((getByRole('button') as HTMLButtonElement).disabled).toBe(true);
	});
	it('EmptyState shows title', () => {
		const { getByText } = render(EmptyState, { props: { title: '无数据' } });
		expect(getByText('无数据')).toBeTruthy();
	});
	it('StatusDot shows its label text (color is not the only signal)', () => {
		const { getByText } = render(StatusDot, { props: { tone: 'ok', label: 'Connected' } });
		expect(getByText('Connected')).toBeTruthy();
	});
});
```
> Snippet 在 vitest 里不便直接构造;`Button` 测试用 `children` 占位转 `never` 仅验证 disabled 行为。若 `@testing-library/svelte` 对 Snippet 渲染报错,改为只测 `EmptyState`/`StatusDot`(不传 children 的 Button 用 `IconButton` 替代验证),保持至少 2 个断言绿。

- [ ] **Step 10: 跑测试 + 校验**

Run: `npx vitest run src/lib/components/ui/ui.test.ts && npm run check`
Expected: PASS;svelte-check 0 errors。

- [ ] **Step 11: Commit**

```bash
git add dashboard/web/src/lib/components/ui/
git commit -F - <<'EOF'
feat(P2.k/dash): 基础展示组件库(手写)

src/lib/components/ui/:Button(primary/secondary/ghost/danger + loading)、
IconButton、Input(invalid 态)、Textarea、Field(label+hint+error)、Card、
Badge(6 tone)、StatusDot(色+文字,色非唯一信号)、Skeleton、EmptyState、
CopyButton。全部走 token 工具类(bg-card/text-fg/border-border/bg-brand…),
focus-visible 可见焦点环。桶导出 index.ts。

EOF
```

---

### Task 3: Toast(svelte-sonner)+ ConfirmDialog(bits-ui)

**Files:**
- Create: `dashboard/web/src/lib/components/ui/Toaster.svelte`
- Create: `dashboard/web/src/lib/ui/toast.ts`
- Create: `dashboard/web/src/lib/components/ui/ConfirmDialog.svelte`
- Modify: `dashboard/web/src/lib/components/ui/index.ts`(加导出)
- Test: `dashboard/web/src/lib/ui/toast.test.ts`

- [ ] **Step 1: Toaster + toast 帮助**

Create `dashboard/web/src/lib/components/ui/Toaster.svelte`:
```svelte
<script lang="ts">
	import { Toaster } from 'svelte-sonner';
</script>

<Toaster
	position="bottom-right"
	toastOptions={{
		classes: {
			toast: 'rounded-lg border border-border bg-card text-fg text-sm',
			error: 'border-danger/40',
			success: 'border-success/40'
		}
	}}
/>
```

Create `dashboard/web/src/lib/ui/toast.ts`(薄封装,集中样式语义):
```ts
import { toast as sonner } from 'svelte-sonner';

export const toast = {
	success: (msg: string) => sonner.success(msg),
	error: (msg: string) => sonner.error(msg),
	info: (msg: string) => sonner.message(msg)
};
```

- [ ] **Step 2: ConfirmDialog(bits-ui Dialog 包装)**

Create `dashboard/web/src/lib/components/ui/ConfirmDialog.svelte`:
```svelte
<script lang="ts">
	import { Dialog } from 'bits-ui';
	import Button from './Button.svelte';
	let {
		open = $bindable(false),
		title,
		description = '',
		confirmLabel = '确认',
		cancelLabel = '取消',
		danger = false,
		onconfirm
	}: {
		open?: boolean;
		title: string;
		description?: string;
		confirmLabel?: string;
		cancelLabel?: string;
		danger?: boolean;
		onconfirm: () => void;
	} = $props();
</script>

<Dialog.Root bind:open>
	<Dialog.Portal>
		<Dialog.Overlay class="fixed inset-0 z-50 bg-black/40" />
		<Dialog.Content
			class="fixed left-1/2 top-1/2 z-50 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-5 shadow-lg"
		>
			<Dialog.Title class="text-sm font-semibold text-fg">{title}</Dialog.Title>
			{#if description}
				<Dialog.Description class="mt-1 text-xs text-muted">{description}</Dialog.Description>
			{/if}
			<div class="mt-5 flex justify-end gap-2">
				<Dialog.Close>
					{#snippet child({ props })}
						<Button variant="secondary" {...props}>{cancelLabel}</Button>
					{/snippet}
				</Dialog.Close>
				<Button
					variant={danger ? 'danger' : 'primary'}
					onclick={() => {
						onconfirm();
						open = false;
					}}>{confirmLabel}</Button
				>
			</div>
		</Dialog.Content>
	</Dialog.Portal>
</Dialog.Root>
```
> bits-ui v1 的 `child` snippet 转发 props 给自定义 trigger/close。若所装 bits-ui 版本 API 不同(如无 `child` snippet),用 `npx ctx7@latest docs /huntabyte/bits-ui "Dialog Close asChild child snippet Svelte 5"` 对齐;接口(open 双向、title/description/onconfirm)不变。

- [ ] **Step 3: 加桶导出**

在 `dashboard/web/src/lib/components/ui/index.ts` 末尾追加:
```ts
export { default as Toaster } from './Toaster.svelte';
export { default as ConfirmDialog } from './ConfirmDialog.svelte';
```

- [ ] **Step 4: toast 帮助测试(mock svelte-sonner)**

Create `dashboard/web/src/lib/ui/toast.test.ts`:
```ts
import { describe, it, expect, vi } from 'vitest';

vi.mock('svelte-sonner', () => ({
	toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() }
}));

import { toast } from './toast';
import { toast as sonner } from 'svelte-sonner';

describe('toast helper', () => {
	it('maps success/error/info to sonner', () => {
		toast.success('a');
		toast.error('b');
		toast.info('c');
		expect((sonner.success as any).mock.calls[0][0]).toBe('a');
		expect((sonner.error as any).mock.calls[0][0]).toBe('b');
		expect((sonner.message as any).mock.calls[0][0]).toBe('c');
	});
});
```

- [ ] **Step 5: 跑测试 + 校验**

Run: `npx vitest run src/lib/ui/toast.test.ts && npm run check && npm run build`
Expected: PASS;svelte-check 0 errors;build 绿(bits-ui Dialog + svelte-sonner 打包通过)。

- [ ] **Step 6: Commit**

```bash
git add dashboard/web/src/lib/components/ui/Toaster.svelte dashboard/web/src/lib/components/ui/ConfirmDialog.svelte dashboard/web/src/lib/ui/toast.ts dashboard/web/src/lib/ui/toast.test.ts dashboard/web/src/lib/components/ui/index.ts
git commit -F - <<'EOF'
feat(P2.k/dash): Toast(svelte-sonner)+ ConfirmDialog(bits-ui)

Toaster(底右,token 上皮)+ toast 帮助(success/error/info 语义封装);
ConfirmDialog 包装 bits-ui Dialog(open 双向、danger 变体、onconfirm 回调),
供设置页改 embedder 重嵌确认用。无障碍由 bits-ui 提供(焦点陷阱/ESC/aria)。

EOF
```

---

### Task 4: 数据原语 createQuery + api.ts 加固

**Files:**
- Modify: `dashboard/web/src/lib/api.ts`(类型化错误 + 超时 + abort)
- Create: `dashboard/web/src/lib/query.svelte.ts`(createQuery 数据原语)
- Test: `dashboard/web/src/lib/api.test.ts`(扩展)
- Test: `dashboard/web/src/lib/query.test.svelte.ts`

- [ ] **Step 1: 加固 api.ts**

替换 `dashboard/web/src/lib/api.ts` 全文:
```ts
import { getToken } from './token';

export class ApiError extends Error {
	constructor(
		public status: number,
		public path: string,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}
	/** 401/403 → 多半是 token 缺失/失效。 */
	get isAuth(): boolean {
		return this.status === 401 || this.status === 403;
	}
}

const TIMEOUT_MS = 15000;

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
	const headers = new Headers(init.headers);
	const tok = getToken();
	if (tok) headers.set('Authorization', `Bearer ${tok}`);
	headers.set('Content-Type', 'application/json');
	const ctrl = new AbortController();
	const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
	try {
		const res = await fetch(path, { ...init, headers, signal: init.signal ?? ctrl.signal });
		if (!res.ok) {
			let detail = res.statusText;
			try {
				const body = await res.json();
				if (body?.detail) detail = String(body.detail);
			} catch {
				/* 非 JSON body,保留 statusText */
			}
			throw new ApiError(res.status, path, `${res.status} ${detail}`);
		}
		return (await res.json()) as T;
	} catch (e) {
		if (e instanceof ApiError) throw e;
		if (e instanceof DOMException && e.name === 'AbortError')
			throw new ApiError(0, path, `请求超时（>${TIMEOUT_MS / 1000}s）`);
		throw new ApiError(0, path, String(e));
	} finally {
		clearTimeout(timer);
	}
}

export const api = {
	get: <T>(p: string, init?: RequestInit) => req<T>(p, init),
	post: <T>(p: string, body: unknown, init?: RequestInit) =>
		req<T>(p, { ...init, method: 'POST', body: JSON.stringify(body) })
};
```

- [ ] **Step 2: createQuery 数据原语**

Create `dashboard/web/src/lib/query.svelte.ts`:
```ts
import { ApiError } from './api';

export type QueryState<T> = {
	readonly data: T | null;
	readonly error: ApiError | null;
	readonly loading: boolean;
	refetch: () => Promise<void>;
};

/**
 * 统一的"载入/空/错"数据原语。传入一个返回 Promise 的 fetcher;
 * 组件读 `q.loading / q.error / q.data` 三态,调 `q.refetch()` 重取。
 * 用 Svelte 5 runes($state),文件名须 `.svelte.ts`。
 */
export function createQuery<T>(fetcher: () => Promise<T>): QueryState<T> {
	let data = $state<T | null>(null);
	let error = $state<ApiError | null>(null);
	let loading = $state(false);

	async function refetch() {
		loading = true;
		try {
			data = await fetcher();
			error = null;
		} catch (e) {
			error = e instanceof ApiError ? e : new ApiError(0, '', String(e));
		} finally {
			loading = false;
		}
	}

	return {
		get data() {
			return data;
		},
		get error() {
			return error;
		},
		get loading() {
			return loading;
		},
		refetch
	};
}
```

- [ ] **Step 3: 扩展 api.test.ts**

替换 `dashboard/web/src/lib/api.test.ts` 全文:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api, ApiError } from './api';
import * as tok from './token';

beforeEach(() => {
	vi.spyOn(tok, 'getToken').mockReturnValue('secret');
	globalThis.fetch = vi.fn(
		async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 })
	) as unknown as typeof fetch;
});

describe('api', () => {
	it('attaches bearer token', async () => {
		await api.get('/api/overview');
		const [, init] = (globalThis.fetch as any).mock.calls[0];
		expect(new Headers(init.headers).get('Authorization')).toBe('Bearer secret');
	});
	it('throws ApiError on non-ok with status + path', async () => {
		globalThis.fetch = vi.fn(
			async () => new Response(JSON.stringify({ detail: 'nope' }), { status: 401 })
		) as any;
		const err = await api.get('/api/overview').catch((e) => e);
		expect(err).toBeInstanceOf(ApiError);
		expect(err.status).toBe(401);
		expect(err.isAuth).toBe(true);
		expect(err.path).toBe('/api/overview');
		expect(String(err.message)).toContain('nope');
	});
});
```

- [ ] **Step 4: createQuery 测试**

Create `dashboard/web/src/lib/query.test.svelte.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { createQuery } from './query.svelte';

describe('createQuery', () => {
	it('moves through loading → data', async () => {
		const q = createQuery(async () => 42);
		expect(q.data).toBe(null);
		const p = q.refetch();
		expect(q.loading).toBe(true);
		await p;
		expect(q.loading).toBe(false);
		expect(q.data).toBe(42);
		expect(q.error).toBe(null);
	});
	it('captures errors as ApiError', async () => {
		const q = createQuery(async () => {
			throw new Error('boom');
		});
		await q.refetch();
		expect(q.error?.message).toContain('boom');
		expect(q.data).toBe(null);
	});
});
```

- [ ] **Step 5: 跑测试**

Run: `npx vitest run src/lib/api.test.ts src/lib/query.test.svelte.ts`
Expected: PASS(api 2 + query 2)。若 `.svelte.ts` 测试需 runes 支持,vitest 已配 `@sveltejs/vite-plugin-svelte`,`$state` 在 `.svelte.ts` 文件可用。

- [ ] **Step 6: Commit**

```bash
git add dashboard/web/src/lib/api.ts dashboard/web/src/lib/query.svelte.ts dashboard/web/src/lib/api.test.ts dashboard/web/src/lib/query.test.svelte.ts
git commit -F - <<'EOF'
feat(P2.k/dash): 数据层加固 — ApiError + 超时/abort + createQuery 原语

api.ts 抛类型化 ApiError(status/path/isAuth,解析后端 {detail});15s 超时
+ AbortController。新增 createQuery(fetcher) runes 原语,暴露 data/error/
loading 三态 + refetch,供各面板统一 载入/空/错,消除每页 ~50 行样板。

EOF
```

---

### Task 5: ws.ts 加固(重连 + 心跳 + 连接状态 store)

**Files:**
- Modify: `dashboard/web/src/lib/ws.ts`(自动重连指数退避 + 心跳 + 状态回调)
- Create: `dashboard/web/src/lib/health.ts`(连接 / LLM / Embedder 健康 store)
- Test: `dashboard/web/src/lib/ws.test.ts`

- [ ] **Step 1: 健康 store**

Create `dashboard/web/src/lib/health.ts`:
```ts
import { writable } from 'svelte/store';

export type Conn = 'connecting' | 'open' | 'closed';
/** WebSocket 连接态(壳顶健康灯之一)。 */
export const wsConn = writable<Conn>('closed');
/** LLM / Embedder 是否已配置(null=未知)。 */
export const llmConfigured = writable<boolean | null>(null);
export const embedderConfigured = writable<boolean | null>(null);
```
> 注意:`llmConfigured` 从旧 `config-store.ts` 迁来。`config-store.ts` 在 Task 8 删除并改所有引用指向 `health.ts`。

- [ ] **Step 2: 加固 ws.ts**

替换 `dashboard/web/src/lib/ws.ts` 全文:
```ts
import { getToken } from './token';
import { wsConn } from './health';

export type WsEvent = { type: string; payload: unknown };

const PING_MS = 25000;
const MAX_BACKOFF_MS = 10000;

/**
 * 连接 /ws,自动重连(指数退避到 10s 封顶)+ 心跳。连接态写入 wsConn store。
 * 返回一个 dispose 函数:调用后停止重连并关闭。
 */
export function connectWs(onEvent: (e: WsEvent) => void): () => void {
	let ws: WebSocket | null = null;
	let pingTimer: ReturnType<typeof setInterval> | null = null;
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let attempt = 0;
	let disposed = false;

	function open() {
		if (disposed) return;
		wsConn.set('connecting');
		const proto = location.protocol === 'https:' ? 'wss' : 'ws';
		ws = new WebSocket(`${proto}://${location.host}/ws`);
		ws.onopen = () => {
			attempt = 0;
			wsConn.set('open');
			const t = getToken();
			if (t) ws?.send(t);
			pingTimer = setInterval(() => {
				if (ws?.readyState === WebSocket.OPEN) ws.send('ping');
			}, PING_MS);
		};
		ws.onmessage = (m) => {
			if (m.data === 'pong') return;
			try {
				onEvent(JSON.parse(m.data));
			} catch {
				/* 忽略畸形帧 */
			}
		};
		ws.onerror = () => ws?.close();
		ws.onclose = () => {
			if (pingTimer) clearInterval(pingTimer);
			wsConn.set('closed');
			if (disposed) return;
			const backoff = Math.min(MAX_BACKOFF_MS, 500 * 2 ** attempt++);
			retryTimer = setTimeout(open, backoff);
		};
	}

	open();
	return () => {
		disposed = true;
		if (pingTimer) clearInterval(pingTimer);
		if (retryTimer) clearTimeout(retryTimer);
		ws?.close();
	};
}
```
> 后端 `/ws` 若不识别 `ping` 文本帧,只会忽略(不回 `pong`);心跳目的是让本地 socket 保活并触发 onclose 检测,不依赖服务端回应。`m.data === 'pong'` 仅为兼容未来服务端心跳。

- [ ] **Step 3: ws 测试(mock WebSocket)**

Create `dashboard/web/src/lib/ws.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { connectWs } from './ws';
import { wsConn } from './health';

class FakeWS {
	static last: FakeWS | null = null;
	onopen: (() => void) | null = null;
	onmessage: ((m: { data: string }) => void) | null = null;
	onerror: (() => void) | null = null;
	onclose: (() => void) | null = null;
	readyState = 1;
	sent: string[] = [];
	constructor(public url: string) {
		FakeWS.last = this;
	}
	send(s: string) {
		this.sent.push(s);
	}
	close() {
		this.readyState = 3;
		this.onclose?.();
	}
}

beforeEach(() => {
	(globalThis as any).WebSocket = FakeWS as any;
	(globalThis as any).WebSocket.OPEN = 1;
	wsConn.set('closed');
});

describe('connectWs', () => {
	it('sets wsConn open on open and parses events', () => {
		const events: unknown[] = [];
		const dispose = connectWs((e) => events.push(e));
		FakeWS.last!.onopen!();
		expect(get(wsConn)).toBe('open');
		FakeWS.last!.onmessage!({ data: JSON.stringify({ type: 'tick', payload: 1 }) });
		expect(events).toEqual([{ type: 'tick', payload: 1 }]);
		dispose();
		expect(get(wsConn)).toBe('closed');
	});
	it('ignores pong frames', () => {
		const events: unknown[] = [];
		connectWs((e) => events.push(e));
		FakeWS.last!.onopen!();
		FakeWS.last!.onmessage!({ data: 'pong' });
		expect(events).toEqual([]);
	});
});
```

- [ ] **Step 4: 跑测试**

Run: `npx vitest run src/lib/ws.test.ts`
Expected: PASS(2)。

- [ ] **Step 5: Commit**

```bash
git add dashboard/web/src/lib/ws.ts dashboard/web/src/lib/health.ts dashboard/web/src/lib/ws.test.ts
git commit -F - <<'EOF'
feat(P2.k/dash): ws 自动重连 + 心跳 + 连接健康 store

ws.ts 加指数退避重连(500ms→10s 封顶)+ 25s 心跳 + dispose;连接态写入
新 health.ts 的 wsConn store(壳顶健康灯)。health.ts 同时承载 llmConfigured/
embedderConfigured(下一 Task 接管旧 config-store)。

EOF
```

---

### Task 6: DataTable 升级(排序/筛选/分页/格式化/状态/a11y)

**Files:**
- Modify: `dashboard/web/src/lib/components/DataTable.svelte`(全量升级,保持 `{rows, columns}` 入参兼容 + 增可选项)
- Test: `dashboard/web/src/lib/components/DataTable.test.ts`

- [ ] **Step 1: 升级 DataTable**

替换 `dashboard/web/src/lib/components/DataTable.svelte` 全文:
```svelte
<script lang="ts">
	import EmptyState from './ui/EmptyState.svelte';
	import Skeleton from './ui/Skeleton.svelte';
	import Input from './ui/Input.svelte';

	let {
		rows = [],
		columns,
		loading = false,
		emptyText = '无数据',
		pageSize = 12,
		filterable = true
	}: {
		rows?: Record<string, unknown>[];
		columns: string[];
		loading?: boolean;
		emptyText?: string;
		pageSize?: number;
		filterable?: boolean;
	} = $props();

	let sortCol = $state('');
	let sortDir = $state<1 | -1>(1);
	let filter = $state('');
	let page = $state(0);

	function fmt(v: unknown): string {
		if (v === null || v === undefined) return '';
		if (typeof v === 'object') return JSON.stringify(v);
		return String(v);
	}

	function toggleSort(c: string) {
		if (sortCol === c) sortDir = sortDir === 1 ? -1 : 1;
		else {
			sortCol = c;
			sortDir = 1;
		}
		page = 0;
	}

	let filtered = $derived(
		filter.trim()
			? rows.filter((r) => columns.some((c) => fmt(r[c]).toLowerCase().includes(filter.toLowerCase())))
			: rows
	);
	let sorted = $derived(
		sortCol
			? [...filtered].sort((a, b) => {
					const av = fmt(a[sortCol]);
					const bv = fmt(b[sortCol]);
					return av < bv ? -sortDir : av > bv ? sortDir : 0;
				})
			: filtered
	);
	let pageCount = $derived(Math.max(1, Math.ceil(sorted.length / pageSize)));
	let pageRows = $derived(sorted.slice(page * pageSize, page * pageSize + pageSize));
</script>

{#if loading}
	<div class="space-y-2">
		{#each Array(4) as _}<Skeleton class="h-8 w-full" />{/each}
	</div>
{:else if rows.length === 0}
	<EmptyState title={emptyText} />
{:else}
	{#if filterable}
		<div class="mb-2 max-w-xs">
			<Input bind:value={filter} placeholder="筛选…" oninput={() => (page = 0)} />
		</div>
	{/if}
	<div class="overflow-x-auto rounded-lg border border-border">
		<table class="w-full text-sm">
			<thead class="bg-surface text-left">
				<tr>
					{#each columns as c}
						<th scope="col" aria-sort={sortCol === c ? (sortDir === 1 ? 'ascending' : 'descending') : 'none'} class="px-3 py-2 font-medium text-muted">
							<button class="inline-flex items-center gap-1 hover:text-fg" onclick={() => toggleSort(c)}>
								{c}{#if sortCol === c}<span aria-hidden="true">{sortDir === 1 ? '↑' : '↓'}</span>{/if}
							</button>
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each pageRows as r}
					<tr class="border-t border-border/60">
						{#each columns as c}<td class="px-3" style="padding-block: var(--row-py)">{fmt(r[c])}</td>{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{#if pageCount > 1}
		<div class="mt-2 flex items-center justify-between text-xs text-muted">
			<span>{sorted.length} 行 · 第 {page + 1}/{pageCount} 页</span>
			<div class="flex gap-1">
				<button class="rounded border border-border px-2 py-1 disabled:opacity-40" disabled={page === 0} onclick={() => (page = Math.max(0, page - 1))}>上一页</button>
				<button class="rounded border border-border px-2 py-1 disabled:opacity-40" disabled={page >= pageCount - 1} onclick={() => (page = Math.min(pageCount - 1, page + 1))}>下一页</button>
			</div>
		</div>
	{/if}
{/if}
```

- [ ] **Step 2: DataTable 测试**

Create `dashboard/web/src/lib/components/DataTable.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import DataTable from './DataTable.svelte';

const rows = [
	{ a: 'beta', b: 2 },
	{ a: 'alpha', b: 1 }
];

describe('DataTable', () => {
	it('shows EmptyState when no rows', () => {
		const { getByText } = render(DataTable, { props: { rows: [], columns: ['a'], emptyText: '空空如也' } });
		expect(getByText('空空如也')).toBeTruthy();
	});
	it('renders headers and rows', () => {
		const { getByText } = render(DataTable, { props: { rows, columns: ['a', 'b'] } });
		expect(getByText('alpha')).toBeTruthy();
		expect(getByText('beta')).toBeTruthy();
	});
	it('shows skeleton when loading', () => {
		const { container } = render(DataTable, { props: { rows: [], columns: ['a'], loading: true } });
		expect(container.querySelector('.animate-pulse')).toBeTruthy();
	});
});
```

- [ ] **Step 3: 跑测试 + 校验**

Run: `npx vitest run src/lib/components/DataTable.test.ts && npm run check`
Expected: PASS(3);svelte-check 0 errors。

- [ ] **Step 4: Commit**

```bash
git add dashboard/web/src/lib/components/DataTable.svelte dashboard/web/src/lib/components/DataTable.test.ts
git commit -F - <<'EOF'
feat(P2.k/dash): DataTable 升级 — 排序/筛选/分页/状态/a11y

列头点击排序(aria-sort)+ 客户端文本筛选 + 分页(pageSize 入参,密度可调);
loading→skeleton、空→EmptyState;行垂直内边距走 --row-py(密度模式)。
保持 {rows, columns} 入参兼容,新增可选 loading/emptyText/pageSize/filterable。
对象单元格暂仍 JSON.stringify(深度格式化留 P2.m 各面板)。

EOF
```

---

### Task 7: StatCard 升级 + CodeBlock 新建

**Files:**
- Modify: `dashboard/web/src/lib/components/StatCard.svelte`(加 trend + hint title)
- Create: `dashboard/web/src/lib/components/CodeBlock.svelte`
- Test: `dashboard/web/src/lib/components/StatCard.test.ts`

- [ ] **Step 1: 升级 StatCard**

替换 `dashboard/web/src/lib/components/StatCard.svelte` 全文:
```svelte
<script lang="ts">
	let {
		label,
		value,
		trend = null,
		hint = ''
	}: {
		label: string;
		value: string | number;
		trend?: number | null;
		hint?: string;
	} = $props();
	let tone = $derived(trend === null || trend === 0 ? 'subtle' : trend > 0 ? 'success' : 'danger');
	const toneClass: Record<string, string> = {
		subtle: 'text-subtle',
		success: 'text-success',
		danger: 'text-danger'
	};
</script>

<div class="rounded-xl border border-border bg-card p-4" title={hint}>
	<div class="text-xs uppercase tracking-wide text-muted">{label}</div>
	<div class="mt-1 flex items-baseline gap-2">
		<span class="text-2xl font-semibold text-fg">{value}</span>
		{#if trend !== null && trend !== 0}
			<span class="text-xs {toneClass[tone]}" aria-hidden="true">{trend > 0 ? '↑' : '↓'}{Math.abs(trend)}</span>
		{/if}
	</div>
</div>
```
> 本期保持 `{label, value}` 入参兼容(trend/hint 可选,缺省即旧行为);真正喂 trend 数据是 P2.m。native `title` 作 tooltip(bits-ui Tooltip 留 P2.m)。

- [ ] **Step 2: CodeBlock(替代裸 `<pre>`)**

Create `dashboard/web/src/lib/components/CodeBlock.svelte`:
```svelte
<script lang="ts">
	import CopyButton from './ui/CopyButton.svelte';
	let {
		content,
		language = 'text',
		collapsible = false,
		maxHeight = '24rem'
	}: { content: string; language?: 'text' | 'json'; collapsible?: boolean; maxHeight?: string } =
		$props();
	let text = $derived(
		language === 'json'
			? (() => {
					try {
						return JSON.stringify(JSON.parse(content), null, 2);
					} catch {
						return content;
					}
				})()
			: content
	);
	let collapsed = $state(collapsible);
</script>

<div class="rounded-lg border border-border bg-surface">
	<div class="flex items-center justify-between border-b border-border px-3 py-1.5">
		<span class="text-xs text-subtle">{language}</span>
		<div class="flex items-center gap-2">
			{#if collapsible}
				<button class="text-xs text-muted hover:text-fg" onclick={() => (collapsed = !collapsed)}
					>{collapsed ? '展开' : '收起'}</button
				>
			{/if}
			<CopyButton {text} />
		</div>
	</div>
	{#if !collapsed}
		<pre
			class="overflow-auto p-3 text-xs font-mono text-fg"
			style="max-height: {maxHeight}">{text}</pre>
	{/if}
</div>
```

- [ ] **Step 3: StatCard 测试**

Create `dashboard/web/src/lib/components/StatCard.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import StatCard from './StatCard.svelte';

describe('StatCard', () => {
	it('renders label and value', () => {
		const { getByText } = render(StatCard, { props: { label: 'statements', value: 42 } });
		expect(getByText('statements')).toBeTruthy();
		expect(getByText('42')).toBeTruthy();
	});
	it('shows up arrow for positive trend', () => {
		const { getByText } = render(StatCard, { props: { label: 'x', value: 1, trend: 2 } });
		expect(getByText('↑2')).toBeTruthy();
	});
});
```

- [ ] **Step 4: 跑测试 + 校验**

Run: `npx vitest run src/lib/components/StatCard.test.ts && npm run check`
Expected: PASS(2);svelte-check 0 errors。

- [ ] **Step 5: Commit**

```bash
git add dashboard/web/src/lib/components/StatCard.svelte dashboard/web/src/lib/components/CodeBlock.svelte dashboard/web/src/lib/components/StatCard.test.ts
git commit -F - <<'EOF'
feat(P2.k/dash): StatCard 升级(trend+hint)+ CodeBlock 新建

StatCard 加可选 trend(↑/↓ + 色,色非唯一信号)+ native title hint,保持
{label,value} 兼容。CodeBlock 替代裸 <pre>:json 自动 pretty-print、可折叠、
可复制、等宽——供 replay/eval/working-set 用。

EOF
```

---

### Task 8: 新壳 +layout.svelte(分组 IA + 当前页高亮 + 健康灯 + 响应式 + Toaster)

**Files:**
- Modify: `dashboard/web/src/lib/health.ts`(加 `lastWsEvent`)
- Modify: `dashboard/web/src/routes/+layout.svelte`(整壳重写)
- Modify: `dashboard/web/src/lib/config-store.ts`(降为 shim 再导出,供 settings 过渡)
- Modify: `dashboard/web/e2e/smoke.spec.ts`(断言分组 + 当前页高亮)

- [ ] **Step 1: health.ts 加 lastWsEvent**

在 `dashboard/web/src/lib/health.ts` 末尾追加:
```ts
import type { WsEvent } from './ws';
/** 壳层单一 ws 连接广播的最近一帧事件;各页面订阅它做增量刷新。 */
export const lastWsEvent = writable<WsEvent | null>(null);
```

- [ ] **Step 2: config-store.ts 降为 shim**

替换 `dashboard/web/src/lib/config-store.ts` 全文(避免删文件导致 settings 暂时编译失败;Task 9 重写 settings 后删除本文件):
```ts
// Deprecated shim — moved to ./health. Kept until settings is migrated (Task 9).
export { llmConfigured } from './health';
```

- [ ] **Step 3: 重写 +layout.svelte**

替换 `dashboard/web/src/routes/+layout.svelte` 全文:
```svelte
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

	// 壳层单一 ws 连接:驱动连接健康灯 + 广播事件给各页面(经 lastWsEvent)。
	$effect(() => {
		const dispose = connectWs((e) => lastWsEvent.set(e));
		return dispose;
	});
	// 配置健康灯:读 /api/config 的 key_set。
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
		$wsConn === 'open' ? 'ok' : $wsConn === 'connecting' ? 'warn' : 'down'
	);
	let connLabel = $derived($wsConn === 'open' ? 'Live' : $wsConn === 'connecting' ? '连接中' : '断开');
	const cfgTone = (v: boolean | null) => (v === true ? 'ok' : v === false ? 'warn' : 'unknown');
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="flex min-h-screen flex-col">
	<!-- 顶栏:品牌 + 健康灯 + 移动菜单 -->
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
		<!-- 侧栏:分组 IA + 当前页高亮 -->
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
```
> Token 输入从侧栏移除——迁入 设置 → Access(Task 9)。`page` 来自 `$app/state`(SvelteKit 2.12+ rune 版,2.57 支持);若该项目 svelte-check 提示 `$app/state` 不存在,退用 `import { page } from '$app/stores'` 并把 `page.url.pathname` 换成 `$page.url.pathname`。

- [ ] **Step 4: 更新 e2e smoke**

替换 `dashboard/web/e2e/smoke.spec.ts` 全文:
```ts
import { test, expect } from '@playwright/test';

// Smoke: 新壳渲染 + 分组导航 + 当前页高亮(API 可能 401,只断言壳)。
test('shell renders grouped nav with active highlight', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('Starling')).toBeVisible();
	// 分组标题
	await expect(page.getByText('观测', { exact: true })).toBeVisible();
	await expect(page.getByText('诊断', { exact: true })).toBeVisible();
	// 导航项(标签保留 总览 / Eval)
	await expect(page.getByRole('link', { name: '总览' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Eval' })).toBeVisible();
	// 当前页高亮:落地在 / 时 总览 链接 aria-current=page
	await expect(page.getByRole('link', { name: '总览' })).toHaveAttribute('aria-current', 'page');
});
```

- [ ] **Step 5: 跑校验**

Run: `npm run check && npm run build && npx playwright test`
Expected: svelte-check 0 errors;build 绿;playwright smoke PASS。

- [ ] **Step 6: Commit**

```bash
git add dashboard/web/src/lib/health.ts dashboard/web/src/lib/config-store.ts dashboard/web/src/routes/+layout.svelte dashboard/web/e2e/smoke.spec.ts
git commit -F - <<'EOF'
feat(P2.k/dash): 新壳 — 分组 IA + 当前页高亮 + 健康灯 + 响应式

+layout.svelte 重写:侧栏按 观测/交互/诊断/设置 4 组分组(替代 12 平铺)+
当前页高亮(aria-current,$app/state page)+ 顶栏三盏健康灯(连接/LLM/Embedder,
StatusDot 色+文字)+ 移动端抽屉 + Toaster 挂载。壳层单一 ws 连接驱动连接灯并
经 lastWsEvent 广播给页面。Token 输入移出侧栏(迁 设置→Access)。config-store
降为 health 的 shim(Task 9 删)。e2e smoke 断言分组 + 高亮。

EOF
```

---

### Task 9: 设置页 reshell + 组件级升级(show/hide / 校验 / save toast / 重嵌确认 / Token→Access)

**Files:**
- Create: `dashboard/web/src/lib/ui/validate.ts`(必填校验帮助)
- Test: `dashboard/web/src/lib/ui/validate.test.ts`
- Modify: `dashboard/web/src/routes/settings/+page.svelte`(整页重写)
- Delete: `dashboard/web/src/lib/config-store.ts`(settings 迁走后删)

- [ ] **Step 1: 校验帮助 + 测试**

Create `dashboard/web/src/lib/ui/validate.ts`:
```ts
/** 返回缺失的必填字段名。LLM:key 必填(否则无法抽取);Embedder:key 选填(无则 stub)。 */
export function missingFields(
	p: { model: string },
	opts: { keyRequired: boolean; keySet: boolean; keyInput: string }
): string[] {
	const miss: string[] = [];
	if (!p.model.trim()) miss.push('model');
	if (opts.keyRequired && !opts.keySet && !opts.keyInput.trim()) miss.push('api_key');
	return miss;
}
```

Create `dashboard/web/src/lib/ui/validate.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { missingFields } from './validate';

describe('missingFields', () => {
	it('flags empty model', () => {
		expect(missingFields({ model: '' }, { keyRequired: false, keySet: false, keyInput: '' })).toContain(
			'model'
		);
	});
	it('requires api_key only when keyRequired and not already set/typed', () => {
		expect(
			missingFields({ model: 'gpt' }, { keyRequired: true, keySet: false, keyInput: '' })
		).toContain('api_key');
		expect(
			missingFields({ model: 'gpt' }, { keyRequired: true, keySet: true, keyInput: '' })
		).toEqual([]);
		expect(
			missingFields({ model: 'gpt' }, { keyRequired: false, keySet: false, keyInput: '' })
		).toEqual([]);
	});
});
```

- [ ] **Step 2: 重写 settings 页**

替换 `dashboard/web/src/routes/settings/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { llmConfigured, embedderConfigured } from '$lib/health';
	import { getToken, setToken } from '$lib/token';
	import { toast } from '$lib/ui/toast';
	import { missingFields } from '$lib/ui/validate';
	import { Button, IconButton, Input, Field, Card, CopyButton, ConfirmDialog } from '$lib/components/ui';

	type Prov = { model: string; base_url: string; key_set?: boolean; dim?: number };
	let llm = $state<Prov>({ model: '', base_url: '' });
	let llmKey = $state('');
	let showLlmKey = $state(false);
	let emb = $state<Prov>({ model: '', base_url: '', dim: 1024 });
	let embKey = $state('');
	let showEmbKey = $state(false);
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
				<div class="flex gap-2">
					<Input
						id="llm-key"
						type={showLlmKey ? 'text' : 'password'}
						bind:value={llmKey}
						invalid={errors['llm.api_key']}
						placeholder={llm.key_set ? '已设置 · 留空不改' : 'api_key'}
					/>
					<IconButton aria-label="显示/隐藏" onclick={() => (showLlmKey = !showLlmKey)}>{showLlmKey ? '🙈' : '👁'}</IconButton>
				</div>
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
				<div class="flex gap-2">
					<Input
						id="emb-key"
						type={showEmbKey ? 'text' : 'password'}
						bind:value={embKey}
						placeholder={emb.key_set ? '已设置 · 留空不改' : 'api_key（可空）'}
					/>
					<IconButton aria-label="显示/隐藏" onclick={() => (showEmbKey = !showEmbKey)}>{showEmbKey ? '🙈' : '👁'}</IconButton>
				</div>
			</Field>
		</div>
	</Card>

	<Button loading={saving} onclick={onSaveClick}>保存</Button>

	<Card title="Access">
		<div class="space-y-3">
			<Field label="API Token" for="tok" hint="粘贴 #token=… 登录 URL，或在此直接输入">
				<div class="flex gap-2">
					<Input id="tok" bind:value={token} placeholder="bearer token" />
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
```

- [ ] **Step 3: 删除 config-store shim**

Run:
```bash
git rm dashboard/web/src/lib/config-store.ts
```
Expected: 文件删除。确认无残留引用:
```bash
grep -rn "config-store" dashboard/web/src
```
Expected: 无输出(+layout 与 settings 都已改用 `$lib/health`)。

- [ ] **Step 4: 跑校验**

Run: `npx vitest run src/lib/ui/validate.test.ts && npm run check && npm run build`
Expected: validate 2 PASS;svelte-check 0 errors;build 绿。

- [ ] **Step 5: Commit**

```bash
git add dashboard/web/src/lib/ui/validate.ts dashboard/web/src/lib/ui/validate.test.ts dashboard/web/src/routes/settings/+page.svelte
git commit -F - <<'EOF'
feat(P2.k/dash): 设置页 reshell — show/hide / 校验 / save toast / 重嵌确认 / Token→Access

设置页改用新组件(Card/Field/Input/Button/IconButton/ConfirmDialog):api_key
显示/隐藏切换;必填字段级校验(model 必填、LLM key 必填、embedder key 选填提示
走 stub);保存改 toast 反馈 + loading 态;改 embedder 弹 ConfirmDialog 重嵌确认;
Token 输入迁入 Access 卡(含复制 + 粘贴说明)。删除 config-store shim(改用
health)。本期仍单一 OpenAI 兼容字段(provider 预设/测连通是 P2.l)。

EOF
```

---

### Task 10: 套壳 观测组(overview / statements / cognizers / commitments)

**Files:**
- Modify: `dashboard/web/src/routes/+page.svelte`
- Modify: `dashboard/web/src/routes/statements/+page.svelte`
- Modify: `dashboard/web/src/routes/cognizers/+page.svelte`
- Modify: `dashboard/web/src/routes/commitments/+page.svelte`

> 套壳原则:保留各页 fetch 数据契约,只换成 `createQuery` + 新组件 + 统一 载入/空/错。**不**做深度信息重构(P2.m)。

- [ ] **Step 1: overview(`/+page.svelte`,接 lastWsEvent 实时刷新)**

替换 `dashboard/web/src/routes/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import { lastWsEvent } from '$lib/health';
	import StatCard from '$lib/components/StatCard.svelte';
	import { Card, Skeleton, EmptyState } from '$lib/components/ui';

	type Overview = {
		counts: Record<string, number>;
		commitments_by_state: Record<string, number>;
		queue_by_status: Record<string, number>;
	};
	const q = createQuery(() => api.get<Overview>('/api/overview'));
	$effect(() => {
		q.refetch();
	});
	$effect(() => {
		const e = $lastWsEvent;
		if (e && (e.type === 'tick' || e.type === 'statement_added')) q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">总览</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="grid grid-cols-2 gap-3 md:grid-cols-3">
		{#each Array(6) as _}<Skeleton class="h-20 w-full" />{/each}
	</div>
{:else if q.data}
	<div class="space-y-6">
		<div class="grid grid-cols-2 gap-3 md:grid-cols-3">
			{#each Object.entries(q.data.counts) as [k, v]}<StatCard label={k} value={v} />{/each}
		</div>
		<Card title="承诺分态">
			<div class="grid grid-cols-3 gap-3 md:grid-cols-6">
				{#each Object.entries(q.data.commitments_by_state) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
		<Card title="队列状态">
			<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
				{#each Object.entries(q.data.queue_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
	</div>
{/if}
```

- [ ] **Step 2: statements**

替换 `dashboard/web/src/routes/statements/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Button, Input } from '$lib/components/ui';

	let predicate = $state('');
	let perspective = $state('');
	function url() {
		const p = new URLSearchParams();
		if (predicate) p.set('predicate', predicate);
		if (perspective) p.set('perspective', perspective);
		return `/api/statements?${p}`;
	}
	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>(url()));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Statements</h1>
<div class="mb-3 flex gap-2">
	<Input bind:value={predicate} placeholder="predicate" class="max-w-40" />
	<Input bind:value={perspective} placeholder="perspective" class="max-w-40" />
	<Button variant="secondary" onclick={() => q.refetch()}>筛选</Button>
</div>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<DataTable
	rows={q.data?.rows ?? []}
	loading={q.loading}
	emptyText="无 statements"
	columns={['holder_id', 'holder_perspective', 'subject_id', 'predicate', 'object_value', 'modality', 'polarity']}
/>
```

- [ ] **Step 3: cognizers**

替换 `dashboard/web/src/routes/cognizers/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import Graph from '$lib/components/Graph.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Card } from '$lib/components/ui';

	type Cognizer = { id: string; canonical_name: string; kind: string; last_seen_at: string };
	type Relation = { a_id: string; b_id: string; affinity: number; power_asymmetry: number };
	const q = createQuery(() => api.get<{ nodes: Cognizer[]; relations: Relation[] }>('/api/cognizers'));
	$effect(() => {
		q.refetch();
	});
	let gnodes = $derived((q.data?.nodes ?? []).map((n) => ({ id: n.id, label: n.canonical_name })));
	let gedges = $derived((q.data?.relations ?? []).map((r) => ({ a: r.a_id, b: r.b_id })));
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Cognizer 社会图</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<div class="space-y-4">
	<Card>
		<Graph nodes={gnodes} edges={gedges} />
	</Card>
	<DataTable
		rows={q.data?.nodes ?? []}
		loading={q.loading}
		emptyText="无 cognizer"
		columns={['canonical_name', 'kind', 'last_seen_at']}
	/>
</div>
```

- [ ] **Step 4: commitments**

替换 `dashboard/web/src/routes/commitments/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Badge } from '$lib/components/ui';

	const STATES = ['created', 'ACTIVE', 'FULFILLED', 'BROKEN', 'RENEGOTIATED', 'WITHDRAWN'];
	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>('/api/commitments'));
	$effect(() => {
		q.refetch();
	});
	let byState = $derived(
		STATES.map((s) => ({ s, n: (q.data?.rows ?? []).filter((r) => r.state === s).length }))
	);
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Commitment 五态机</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<div class="mb-4 flex flex-wrap gap-2">
	{#each byState as b}<Badge tone={b.n ? 'brand' : 'neutral'}>{b.s}: {b.n}</Badge>{/each}
</div>
<DataTable
	rows={q.data?.rows ?? []}
	loading={q.loading}
	emptyText="无 commitment"
	columns={['state', 'subject_id', 'predicate', 'object_value', 'broken_count', 'deadline', 'updated_at']}
/>
```

- [ ] **Step 5: 校验 + Commit**

Run: `npm run check && npm run build`
Expected: svelte-check 0 errors;build 绿。

```bash
git add dashboard/web/src/routes/+page.svelte dashboard/web/src/routes/statements/+page.svelte dashboard/web/src/routes/cognizers/+page.svelte dashboard/web/src/routes/commitments/+page.svelte
git commit -F - <<'EOF'
feat(P2.k/dash): 套壳 观测组(overview/statements/cognizers/commitments)

四面板改用 createQuery 三态 + 新组件(Card/StatCard/Badge/DataTable/Skeleton/
EmptyState):overview 接 lastWsEvent 实时刷新 + skeleton;statements/commitments/
cognizers 走升级版 DataTable(排序/筛选/分页/空/载入)。保留各自数据契约,不做
深度信息重构(P2.m)。

EOF
```

---

### Task 11: 套壳 交互组(interact / working-set / reminders)

**Files:**
- Modify: `dashboard/web/src/routes/interact/+page.svelte`
- Modify: `dashboard/web/src/routes/working-set/+page.svelte`
- Modify: `dashboard/web/src/routes/reminders/+page.svelte`

- [ ] **Step 1: interact**

替换 `dashboard/web/src/routes/interact/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { toast } from '$lib/ui/toast';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Button, Textarea, Input, Badge, Card } from '$lib/components/ui';

	let text = $state('');
	let query = $state('');
	let remembered = $state<string[]>([]);
	let outcome = $state('');
	let results = $state<Record<string, unknown>[]>([]);
	let recalled = $state(false);
	let busyR = $state(false);
	let busyQ = $state(false);

	async function remember() {
		busyR = true;
		try {
			const r = await api.post<{ statement_ids: string[]; outcome: string }>('/api/remember', { text });
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
			const r = await api.post<{ results: Record<string, unknown>[] }>('/api/recall', { query });
			results = r.results;
			recalled = true;
		} catch (e) {
			toast.error(String((e as ApiError).message));
		} finally {
			busyQ = false;
		}
	}
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">交互</h1>
<div class="max-w-2xl space-y-4">
	<Card title="Remember">
		<div class="space-y-2">
			<Textarea bind:value={text} rows={3} placeholder="记一段话…" />
			<div class="flex items-center gap-3">
				<Button loading={busyR} onclick={remember}>记住</Button>
				{#if remembered.length}<span class="text-xs text-muted">{outcome} · {remembered.length} statements</span>{/if}
			</div>
			{#if remembered.length}
				<div class="flex flex-wrap gap-1">
					{#each remembered as id}<Badge tone="brand">{id}</Badge>{/each}
				</div>
			{/if}
		</div>
	</Card>
	<Card title="Recall">
		<div class="space-y-2">
			<div class="flex gap-2">
				<Input bind:value={query} placeholder="query" />
				<Button loading={busyQ} variant="secondary" onclick={recall}>检索</Button>
			</div>
			{#if recalled}
				<DataTable rows={results} emptyText="无召回结果" columns={['subject', 'predicate', 'object', 'score']} />
			{/if}
		</div>
	</Card>
</div>
```

- [ ] **Step 2: working-set(token 预算 + 复制为 prompt + CodeBlock)**

替换 `dashboard/web/src/routes/working-set/+page.svelte` 全文:
```svelte
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
```

- [ ] **Step 3: reminders**

替换 `dashboard/web/src/routes/reminders/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';

	const q = createQuery(() => api.get<{ rows: Record<string, unknown>[] }>('/api/commitments'));
	$effect(() => {
		q.refetch();
	});
	let rows = $derived(
		(q.data?.rows ?? []).filter((r) => r.state === 'ACTIVE' || r.state === 'created')
	);
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">承诺提醒（pending / ACTIVE）</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
<DataTable
	{rows}
	loading={q.loading}
	emptyText="无待办承诺"
	columns={['state', 'subject_id', 'predicate', 'object_value', 'deadline']}
/>
```

- [ ] **Step 4: 校验 + Commit**

Run: `npm run check && npm run build`
Expected: svelte-check 0 errors;build 绿。

```bash
git add dashboard/web/src/routes/interact/+page.svelte dashboard/web/src/routes/working-set/+page.svelte dashboard/web/src/routes/reminders/+page.svelte
git commit -F - <<'EOF'
feat(P2.k/dash): 套壳 交互组(interact/working-set/reminders)

interact 改卡片 + loading 按钮 + 抽取语句 chips(Badge)+ 错误走 toast;
working-set 加 token 预算合计 + 分块 Badge + 一键复制为 prompt + CodeBlock(替代
裸 pre)+ 空态;reminders 走升级 DataTable + 清晰空态。保留数据契约。

EOF
```

---

### Task 12: 套壳 诊断组(queues / conflicts / replay / eval)

**Files:**
- Modify: `dashboard/web/src/routes/queues/+page.svelte`
- Modify: `dashboard/web/src/routes/conflicts/+page.svelte`
- Modify: `dashboard/web/src/routes/replay/+page.svelte`
- Modify: `dashboard/web/src/routes/eval/+page.svelte`

- [ ] **Step 1: queues**

替换 `dashboard/web/src/routes/queues/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import StatCard from '$lib/components/StatCard.svelte';
	import { Card, Skeleton, EmptyState } from '$lib/components/ui';

	type QueueData = {
		dispatch: Record<string, number>;
		embedding_backlog: number;
		vectors_by_status: Record<string, number>;
	};
	const q = createQuery(() => api.get<QueueData>('/api/queues'));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">队列 / 运维</h1>
{#if q.error}
	<EmptyState title="加载失败" description={q.error.message} />
{:else if q.loading && !q.data}
	<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
		{#each Array(4) as _}<Skeleton class="h-20 w-full" />{/each}
	</div>
{:else if q.data}
	<div class="space-y-6">
		<StatCard label="embedding backlog" value={q.data.embedding_backlog} hint="待嵌入语句数" />
		<Card title="Outbox dispatch">
			<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
				{#each Object.entries(q.data.dispatch) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
		<Card title="向量状态">
			<div class="grid grid-cols-2 gap-3 md:grid-cols-4">
				{#each Object.entries(q.data.vectors_by_status) as [k, v]}<StatCard label={k} value={v} />{/each}
			</div>
		</Card>
	</div>
{/if}
```

- [ ] **Step 2: conflicts**

替换 `dashboard/web/src/routes/conflicts/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import { Badge } from '$lib/components/ui';

	type ConflictData = { by_kind: Record<string, number>; conflicts: Record<string, unknown>[] };
	const q = createQuery(() => api.get<ConflictData>('/api/conflicts'));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">ConflictProbe</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
{#if q.data}
	<div class="mb-4 flex flex-wrap gap-2">
		{#each Object.entries(q.data.by_kind) as [k, v]}<Badge tone={v ? 'warn' : 'neutral'}>{k}: {v}</Badge>{/each}
	</div>
{/if}
<DataTable
	rows={q.data?.conflicts ?? []}
	loading={q.loading}
	emptyText="无冲突"
	columns={['src_id', 'dst_id', 'edge_kind', 'weight']}
/>
```

- [ ] **Step 3: replay(scheduler 走 CodeBlock json)**

替换 `dashboard/web/src/routes/replay/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import DataTable from '$lib/components/DataTable.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import { Card } from '$lib/components/ui';

	type ReplayData = {
		scheduler: Record<string, unknown>;
		ledger: Record<string, unknown>[];
		windows: Record<string, unknown>[];
	};
	const q = createQuery(() => api.get<ReplayData>('/api/replay'));
	$effect(() => {
		q.refetch();
	});
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Replay / Reconsolidation</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
{#if q.data}
	<div class="space-y-4">
		<Card title="调度器">
			<CodeBlock content={JSON.stringify(q.data.scheduler)} language="json" collapsible />
		</Card>
		<div>
			<h2 class="mb-2 text-sm font-semibold text-muted">Ledger</h2>
			<DataTable
				rows={q.data.ledger}
				emptyText="无 ledger"
				columns={['replay_batch_id', 'mode', 'sampled_count', 'started_at', 'finished_at']}
			/>
		</div>
		<div>
			<h2 class="mb-2 text-sm font-semibold text-muted">再巩固窗口</h2>
			<DataTable
				rows={q.data.windows}
				emptyText="无窗口"
				columns={['stmt_id', 'opened_at', 'close_deadline', 'status']}
			/>
		</div>
	</div>
{/if}
```

- [ ] **Step 4: eval(报告走 CodeBlock,最新优先,可折叠)**

替换 `dashboard/web/src/routes/eval/+page.svelte` 全文:
```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import { createQuery } from '$lib/query.svelte';
	import CodeBlock from '$lib/components/CodeBlock.svelte';
	import { EmptyState } from '$lib/components/ui';

	type Reports = { reports: { name: string; markdown: string }[] };
	const q = createQuery(() => api.get<Reports>('/api/eval'));
	$effect(() => {
		q.refetch();
	});
	let reports = $derived([...(q.data?.reports ?? [])].reverse());
</script>

<h1 class="mb-4 text-xl font-semibold text-fg">Eval 报告</h1>
{#if q.error}<p class="mb-2 text-sm text-danger">{q.error.message}</p>{/if}
{#if q.data && reports.length === 0}
	<EmptyState title="暂无报告" />
{:else}
	<div class="space-y-3">
		{#each reports as r}
			<div>
				<div class="mb-1 text-sm font-medium text-fg">{r.name}</div>
				<CodeBlock content={r.markdown} language="text" collapsible />
			</div>
		{/each}
	</div>
{/if}
```

- [ ] **Step 5: 校验 + Commit**

Run: `npm run check && npm run build`
Expected: svelte-check 0 errors;build 绿。

```bash
git add dashboard/web/src/routes/queues/+page.svelte dashboard/web/src/routes/conflicts/+page.svelte dashboard/web/src/routes/replay/+page.svelte dashboard/web/src/routes/eval/+page.svelte
git commit -F - <<'EOF'
feat(P2.k/dash): 套壳 诊断组(queues/conflicts/replay/eval)

queues 加 skeleton + 健康框定 StatCard;conflicts 走 Badge + DataTable;
replay scheduler 改 CodeBlock(json pretty + 折叠,替代裸 JSON.stringify),
ledger/windows 走升级 DataTable;eval 报告改 CodeBlock(可折叠、最新优先,
替代裸 pre)。保留数据契约。

EOF
```

---

### Task 13: 全量回归 + 明暗目检

**Files:**
- 无源码改动(验收 + 收尾)

- [ ] **Step 1: 全量自动化测试**

Run:
```bash
cd dashboard/web
npm run check
npm run build
npx vitest run
npx playwright test
```
Expected:
- `svelte-check` 0 errors / 0 warnings。
- `build` 绿。
- `vitest`:全绿,约 21 个用例(token 3 / api 2 / density 1 / ui 3 / toast 1 / query 2 / ws 2 / DataTable 3 / StatCard 2 / validate 2)。数目以实际为准,只增不减、无失败。
- `playwright`:smoke 1 PASS。

- [ ] **Step 2: 明暗双主题目检(预览)**

Run:
```bash
npm run preview
```
然后浏览器开 `http://localhost:4173`,逐项核对(用 OS 浅色/深色各看一遍):
- 壳:分组侧栏(观测/交互/诊断/设置)、当前页高亮、顶栏三盏健康灯(连接/LLM/Embedder,色+文字)。
- 每个面板:有数据时正常;无后端(API 401/超时)时显示 错误/空态 而非白屏或裸报错。
- 设置页:api_key 显示/隐藏切换、必填红框、保存 toast、改 embedder 弹确认框、Access 卡的 Token + 复制。
- 浅色/深色下 token 配色都正常(无对比度坍塌)。
按 Ctrl-C 结束预览。

> 这一步是人工目检,subagent 执行时若无法开浏览器,则跳过预览、只跑 Step 1 自动化,并在完成报告里注明"明暗目检留人工"。

- [ ] **Step 3: 确认改动范围干净(只在 dashboard/web 下)**

Run:
```bash
cd /Users/jaredguo-mini/develop/memory/starling/.claude/worktrees/p2-k-dashboard-foundation
git diff --stat origin/main -- . | tail -5
git status -s
```
Expected:所有改动路径都在 `dashboard/web/` 下;工作树干净(全部已提交);与并行 p2-c 的 C++/构建文件零重叠。

- [ ] **Step 4: 完成报告(不自动合并)**

不在本 plan 内合并 main / 改 roadmap。向用户报告 P2.k 完成:测试数、改动文件清单、明暗目检结论。**合并 main + roadmap 登记 P2.k + 提交本 plan 文件**都是里程碑收尾动作,需用户显式 consent(且按约定 `dangerouslyDisableSandbox` + explicit-path)。

---

## Self-Review(对照 spec §8 P2.k)

**1. Spec 覆盖:**
- 设计 token(slate+indigo+语义色,明暗等价,密度模式)→ Task 1 ✓
- bits-ui + 组件库(手写基础件 + Dialog/Toast)→ Task 2、3 ✓(Tabs/Tooltip/Select/Combobox/Switch 按 YAGNI 延到 P2.l/P2.m,见下"范围说明")
- createQuery + api/ws 加固 → Task 4、5 ✓
- DataTable 升级 / StatCard 升级 / CodeBlock → Task 6、7 ✓
- 新壳:分组 IA + 当前页高亮 + 三盏健康灯 + 响应式 + token→Access → Task 8、9 ✓
- 设置页组件级升级(show/hide、校验、save toast、重嵌确认弹窗)→ Task 9 ✓
- 全 12 面板套壳统一态 → Task 8(settings 壳)、9(settings)、10(观测 4)、11(交互 3)、12(诊断 4)= 12 ✓
- 测试 vitest + playwright → 各 Task 内置 + Task 13 全量 ✓

**2. Placeholder 扫描:** 无 TBD/TODO;每个改文件都给了确切全文或确切追加块;每步有 Run 命令 + 期望输出 + commit HEREDOC。✓

**3. 类型/命名一致性:**
- `createQuery<T>()` 返回 `{data,error,loading,refetch}`,各页面统一用 `q.data?` / `q.loading` / `q.error.message` / `q.refetch()`。✓
- `ApiError`(status/path/isAuth/message)在 api.ts 定义,settings/interact/working-set catch 时 `(e as ApiError).message`。✓
- `health.ts` 导出 `wsConn / llmConfigured / embedderConfigured / lastWsEvent`;+layout 与 settings 都从 `$lib/health` 引;`config-store.ts` 先 shim(Task 8)后删(Task 9)。✓
- 组件 props 名(`tone/label/loading/variant/invalid/title/open/onconfirm`)在定义(Task 2、3、6、7)与使用(Task 8–12)处一致。✓
- DataTable 入参 `{rows, columns, loading?, emptyText?, pageSize?, filterable?}`——旧调用只传 `{rows, columns}` 仍兼容,新调用加 `loading/emptyText`。✓

**范围说明(YAGNI,写入完成报告供 P2.l/P2.m 衔接):** P2.k 只引入 bits-ui 的 Dialog + svelte-sonner 的 Toast;Tabs/Tooltip/Select/Combobox/Switch/DropdownMenu 延到真正需要的面板(provider 预设 Select 属 P2.l;StatCard Tooltip、深度面板交互属 P2.m)。手动明暗开关、DataTable 对象单元格深度格式化、Graph 交互升级,均属 P2.m。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-08-p2-k-dashboard-foundation.md`(保留 untracked 直到 P2.k 收尾)。

两种执行方式:
1. **Subagent-Driven(推荐)** — 每个 Task 派一个 fresh subagent,两阶段 review(spec 合规 → 代码质量),快速迭代,本会话内完成。
2. **Inline Execution** — 本会话直接按 executing-plans 批量执行 + checkpoint。

按你的节奏:先 review 这份 plan,再决定是否走 subagent-driven-development 执行。
