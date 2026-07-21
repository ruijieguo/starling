<script lang="ts">
	// Cognizer 关系图。
	//
	// 重做起因(实测,非猜测):本机 233 个 cognizer 只有 6 条关系边 —— 227 个是孤立点。
	// 旧实现把全部节点等分到一个半径 140 的圆上,于是两百多个标签叠成一圈,既读不了
	// 也点不中。两处根本改动:
	//   1. 孤立点不进关系图。它们在「关系图」里不携带任何关系信息,画进去纯是噪声;
	//      去向明确写在图下方,并在下方表格里可搜索 —— 不能让人以为节点丢了。
	//   2. 画布可缩放 / 平移 / 旋转,标签按缩放级别去拥挤(悬停与选中不受限)。
	// 布局与变换的纯逻辑全在 lib/graph.ts(可测);本组件只负责渲染与交互。
	import {
		kindColorVar,
		kindLabel,
		kindLegend,
		edgeWidth,
		edgeOpacity,
		powerDash,
		relationTooltip,
		partitionByConnectivity,
		layoutForce,
		fitToBox,
		viewTransform,
		counterTransform,
		zoomBy,
		clampZoom,
		normalizeAngle,
		showLabel,
		truncateLabel,
		MIN_ZOOM,
		MAX_ZOOM,
		IDENTITY_VIEW,
		type ViewState
	} from '$lib/graph';

	type Node = { id: string; label: string; kind?: string };
	type Edge = { a: string; b: string; affinity?: number | null; power_asymmetry?: number | null };
	let {
		nodes,
		edges,
		onNodeClick,
		selectedId = null
	}: {
		nodes: Node[];
		edges: Edge[];
		onNodeClick?: (id: string) => void;
		selectedId?: string | null;
	} = $props();

	const W = 640,
		H = 420,
		CX = W / 2,
		CY = H / 2;

	let part = $derived(partitionByConnectivity(nodes.map((n) => n.id), edges));
	// Set 而非 includes:节点数是全量(实测 233),connected 虽小,但 O(n·m) 的写法
	// 会随社会图长大而劣化,没有理由留这个坑。
	let connectedSet = $derived(new Set(part.connected));
	let connectedNodes = $derived(nodes.filter((n) => connectedSet.has(n.id)));
	let pos = $derived(
		fitToBox(layoutForce(part.connected, edges, { width: W, height: H }), {
			width: W,
			height: H,
			margin: 56
		})
	);

	let view = $state<ViewState>({ ...IDENTITY_VIEW });
	let hovered = $state<string | null>(null);
	let legend = kindLegend();
	// 只展示数据里真出现过的 kind —— 全 6 类恒定铺开会让图例比图还长,
	// 且暗示存在实际不存在的分类。
	let presentKinds = $derived(new Set(connectedNodes.map((n) => n.kind ?? '')));
	let shownLegend = $derived(legend.filter((l) => presentKinds.has(l.kind)));

	// ── 平移:指针拖拽 ──────────────────────────────────────────────────────
	let dragging = $state(false);
	let last = { x: 0, y: 0 };

	function onPointerDown(e: PointerEvent) {
		// 只处理画布本身的拖拽;节点上的按下交给节点的 click。
		if ((e.target as Element).closest('[data-node]')) return;
		dragging = true;
		last = { x: e.clientX, y: e.clientY };
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}
	function onPointerMove(e: PointerEvent) {
		if (!dragging) return;
		view.panX += e.clientX - last.x;
		view.panY += e.clientY - last.y;
		last = { x: e.clientX, y: e.clientY };
	}
	function onPointerUp(e: PointerEvent) {
		dragging = false;
		const el = e.currentTarget as Element;
		if (el.hasPointerCapture?.(e.pointerId)) el.releasePointerCapture(e.pointerId);
	}

	function onWheel(e: WheelEvent) {
		e.preventDefault(); // 不让滚轮同时滚动页面
		view.zoom = zoomBy(view.zoom, e.deltaY);
	}

	const nudgeZoom = (f: number) => (view.zoom = clampZoom(view.zoom * f));
	const rotate = (d: number) => (view.rotation = normalizeAngle(view.rotation + d));
	const reset = () => (view = { ...IDENTITY_VIEW });
</script>

{#if connectedNodes.length === 0}
	<div class="rounded-xl border border-dashed border-border p-8 text-center">
		<p class="text-sm font-medium text-fg">还没有任何关系边</p>
		<p class="mt-1 text-xs text-subtle">
			共 {nodes.length} 个认知体,但两两之间尚无 cognizer_relations 记录,因此画不出关系图。
			它们在下方表格中可检索。
		</p>
	</div>
{:else}
	<div class="space-y-2">
		<!-- 控件:缩放 / 旋转 / 复位。旋转用滑杆而非只给按钮,便于连续调节。 -->
		<div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-subtle">
			<div class="flex items-center gap-1">
				<button
					type="button"
					class="rounded-control border border-border px-2 py-0.5 hover:bg-surface"
					onclick={() => nudgeZoom(1 / 1.4)}
					aria-label="缩小">−</button
				>
				<span class="w-12 text-center tabular-nums text-fg">{view.zoom.toFixed(1)}×</span>
				<button
					type="button"
					class="rounded-control border border-border px-2 py-0.5 hover:bg-surface"
					onclick={() => nudgeZoom(1.4)}
					aria-label="放大">+</button
				>
			</div>
			<div class="flex items-center gap-2">
				<label for="graph-rot">旋转</label>
				<input
					id="graph-rot"
					type="range"
					min="0"
					max="359"
					bind:value={view.rotation}
					class="w-32"
				/>
				<span class="w-10 tabular-nums text-fg">{Math.round(view.rotation)}°</span>
			</div>
			<button
				type="button"
				class="rounded-control border border-border px-2 py-0.5 hover:bg-surface"
				onclick={reset}>复位</button
			>
			<span class="text-muted">滚轮缩放 · 拖拽平移 · 点节点看详情</span>
		</div>

		<svg
			viewBox="0 0 {W} {H}"
			class="w-full touch-none select-none rounded-control border border-border bg-surface"
			style="cursor:{dragging ? 'grabbing' : 'grab'}"
			role="application"
			aria-label="Cognizer 关系图:可缩放、平移、旋转;点击节点查看详情"
			onpointerdown={onPointerDown}
			onpointermove={onPointerMove}
			onpointerup={onPointerUp}
			onpointercancel={onPointerUp}
			onwheel={onWheel}
		>
			<!-- snippet 必须定义在 <svg> 之内。定义在组件顶层时,Svelte 按 HTML 命名空间
			     编译它,生成的 <circle> 是 HTMLUnknownElement,在 SVG 里一个像素都不画 ——
			     而 check / vitest / build 三门全绿。实测:节点圆 namespaceURI 是
			     .../1999/xhtml,同页图例圆(直接写在 svg 里)才是 .../2000/svg。 -->
			{#snippet nodeBody(n: Node, isSel: boolean, isHov: boolean)}
				<!-- 命中区比可见圆点大:6px 的圆点很难点中,缩小时尤甚。 -->
				<circle r="14" fill="transparent" />
				{#if isSel || isHov}
					<circle r="10" fill="none" stroke="var(--color-brand)" stroke-width="1.5" />
				{/if}
				<circle r="6" fill={kindColorVar(n.kind)} />
				{#if showLabel(view.zoom, { hovered: isHov, selected: isSel })}
					<!-- paint-order + 同背景色描边 = 廉价的文字底衬,免得标签压在边线上读不清 -->
					<text
						x="11"
						y="4"
						font-size="11"
						fill="currentColor"
						paint-order="stroke"
						stroke="var(--color-surface)"
						stroke-width="3"
						stroke-linejoin="round">{truncateLabel(n.label)}</text
					>
				{/if}
				<title>{n.label} · {kindLabel(n.kind)}</title>
			{/snippet}

			<g transform={viewTransform(view, CX, CY)}>
				{#each edges as e}
					{@const a = pos.get(e.a)}
					{@const b = pos.get(e.b)}
					{#if a && b}
						{@const lit = hovered === e.a || hovered === e.b || selectedId === e.a || selectedId === e.b}
						<line
							x1={a.x}
							y1={a.y}
							x2={b.x}
							y2={b.y}
							stroke={lit ? 'var(--color-brand)' : 'currentColor'}
							stroke-width={edgeWidth(e.affinity) / clampZoom(view.zoom)}
							stroke-opacity={lit ? 0.95 : edgeOpacity(e.affinity)}
							stroke-dasharray={powerDash(e.power_asymmetry)}
						>
							<title>{relationTooltip(e.affinity, e.power_asymmetry)}</title>
						</line>
					{/if}
				{/each}

				{#each connectedNodes as n}
					{@const p = pos.get(n.id)}
					{#if p}
						{@const isSel = selectedId === n.id}
						{@const isHov = hovered === n.id}
						<g transform={`translate(${p.x},${p.y})`}>
							<!-- 反变换:抵消画布的缩放与旋转,让圆点大小恒定、标签始终水平。
							     没有它,放大时标签会涨成巨幅文字,旋转时还会倒过来。 -->
							<g transform={counterTransform(view)}>
								<!-- role/tabindex 必须是字面量,写成三元 svelte-check 静态分析不出
								     「role 一定是 button」,会报 a11y_no_noninteractive_tabindex。
								     旧实现为此把整个节点块复制了两份;这里用 snippet 共用本体,
								     只让两个薄壳不同。 -->
								{#if onNodeClick}
									<g
										data-node
										role="button"
										tabindex="0"
										aria-label={n.label}
										style="cursor:pointer"
										onclick={() => onNodeClick(n.id)}
										onkeydown={(e) => {
											if (e.key === 'Enter' || e.key === ' ') {
												e.preventDefault();
												onNodeClick(n.id);
											}
										}}
										onpointerenter={() => (hovered = n.id)}
										onpointerleave={() => (hovered = null)}
										onfocus={() => (hovered = n.id)}
										onblur={() => (hovered = null)}
									>
										{@render nodeBody(n, isSel, isHov)}
									</g>
								{:else}
									<g data-node>{@render nodeBody(n, isSel, isHov)}</g>
								{/if}
							</g>
						</g>
					{/if}
				{/each}
			</g>

			{#if shownLegend.length}
				<g transform="translate(10,{H - 14})">
					{#each shownLegend as item, i}
						<g transform={`translate(${i * 64},0)`}>
							<circle r="4" cx="4" cy="4" fill={item.colorVar} />
							<text x="11" y="7" font-size="9" fill="currentColor">{item.label}</text>
						</g>
					{/each}
				</g>
			{/if}
		</svg>

		<p class="text-xs text-subtle">
			图中 {connectedNodes.length} 个认知体有关系边{#if part.isolated.length}；另有
				<span class="text-fg">{part.isolated.length}</span>
				个没有任何关系边,不画入关系图(画进来只是噪声),可在下方表格检索{/if}。
			标签在放大 1.6× 后显示,悬停或选中的节点始终显示。
		</p>
	</div>
{/if}
