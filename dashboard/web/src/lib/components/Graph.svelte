<script lang="ts">
	// T0e ① — 节点按 CognizerKind 着色 + 图例。T3 — 边按 affinity 粗细/透明度、
	// power_asymmetry 虚线标方向,tooltip 显 relation 详情。纯映射逻辑在 graph.ts
	// (可测);本组件只负责渲染 + 既有径向布局(未升级力导向,见文件尾注)。
	import { kindColorVar, kindLabel, kindLegend, edgeWidth, edgeOpacity, powerDash, relationTooltip } from '$lib/graph';

	type Node = { id: string; label: string; kind?: string };
	type Edge = { a: string; b: string; affinity?: number | null; power_asymmetry?: number | null };
	let {
		nodes,
		edges,
		onNodeClick
	}: { nodes: Node[]; edges: Edge[]; onNodeClick?: (id: string) => void } = $props();
	const R = 140,
		CX = 200,
		CY = 170;
	let pos = $derived(
		new Map(
			nodes.map((n, i) => {
				const t = (2 * Math.PI * i) / Math.max(1, nodes.length);
				return [n.id, { x: CX + R * Math.cos(t), y: CY + R * Math.sin(t) }];
			})
		)
	);
	let legend = kindLegend();
</script>

<svg
	viewBox="0 0 400 380"
	class="w-full max-w-lg"
	role={onNodeClick ? 'group' : 'img'}
	aria-label={onNodeClick ? 'Cognizer 关系图，点击节点看详情' : 'Cognizer 关系图'}
>
	{#each edges as e}
		{@const a = pos.get(e.a)}
		{@const b = pos.get(e.b)}
		{#if a && b}
			<line
				x1={a.x}
				y1={a.y}
				x2={b.x}
				y2={b.y}
				stroke="currentColor"
				stroke-width={edgeWidth(e.affinity)}
				stroke-opacity={edgeOpacity(e.affinity)}
				stroke-dasharray={powerDash(e.power_asymmetry)}
			>
				<title>{relationTooltip(e.affinity, e.power_asymmetry)}</title>
			</line>
		{/if}
	{/each}
	{#each nodes as n}
		{@const p = pos.get(n.id)}
		{#if p}
			{#if onNodeClick}
				<g
					transform={`translate(${p.x},${p.y})`}
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
				>
					<circle r="6" fill={kindColorVar(n.kind)} />
					<text x="9" y="4" font-size="10" fill="currentColor">{n.label}</text>
					<title>{n.label} · {kindLabel(n.kind)}</title>
				</g>
			{:else}
				<g transform={`translate(${p.x},${p.y})`}>
					<circle r="6" fill={kindColorVar(n.kind)} />
					<text x="9" y="4" font-size="10" fill="currentColor">{n.label}</text>
					<title>{n.label} · {kindLabel(n.kind)}</title>
				</g>
			{/if}
		{/if}
	{/each}
	<g transform="translate(8,352)">
		{#each legend as item, i}
			<g transform={`translate(${i * 64},0)`}>
				<circle r="4" cx="4" cy="4" fill={item.colorVar} />
				<text x="11" y="7" font-size="9" fill="currentColor">{item.label}</text>
			</g>
		{/each}
	</g>
</svg>

<!--
	布局取舍(T0e+T3 报告 flag):D2 决策要求升级为力导向图,但 package.json 无
	现成力导向/图布局依赖(d3-force 等),引入属于新依赖——按 brief 约束「优先
	数据映射落地」,本次保留既有固定径向布局(R/CX/CY 不变),只做 kind 着色 +
	affinity/power 边映射。力导向布局留给控制器决定是否单列任务(需批准新依赖或
	手写力学模拟,工作量与本任务的数据映射不对等)。
-->

