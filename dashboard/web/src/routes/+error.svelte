<script lang="ts">
	// 应用壳级 error boundary(T9):任一路由的 load/render 抛错时兜底,避免整页白屏
	// (历史事故:undefined bind 导致白屏整页,见 +layout.svelte 注释)。
	// 本组件渲染在 +layout.svelte 的 {@render children()} 之内 → 侧边导航与页头自动保留,
	// 用户可直接换页,不必手改地址栏。
	import { page } from '$app/state';
	import { Button, EmptyState } from '$lib/components/ui';

	let notFound = $derived(page.status === 404);
	let title = $derived(`${page.status} · ${notFound ? '页面不存在' : '出错了'}`);
	// 缺失 message 时给克制兜底文案,不臆测原因。
	let description = $derived(
		page.error?.message?.trim() || (notFound ? '该地址没有对应的页面。' : '没有更多错误信息。')
	);

	// 回总览须是真链接(<a href>),故不能用渲染 <button> 的 Button 组件;
	// 这里对齐 Button 的 secondary 变体样式,不引入新组件。
	const linkClass =
		'inline-flex items-center justify-center gap-2 rounded-control border border-border bg-card px-3 py-1.5 text-sm font-medium text-fg transition hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand';
</script>

<div class="mx-auto max-w-md py-10">
	<EmptyState {title} {description}>
		<div class="flex flex-wrap items-center justify-center gap-2">
			{#if !notFound}
				<!-- 组件树此时已崩,invalidateAll() 不可靠 → 整页重载。404 不给重试(重试无意义)。 -->
				<Button variant="soft" onclick={() => location.reload()}>重试</Button>
			{/if}
			<a href="/" class={linkClass}>返回总览</a>
		</div>
	</EmptyState>
</div>
