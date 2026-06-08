<script lang="ts">
	type Node = { id: string; label: string };
	type Edge = { a: string; b: string };
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
</script>

<svg
	viewBox="0 0 400 340"
	class="w-full max-w-lg"
	role={onNodeClick ? 'group' : 'img'}
	aria-label={onNodeClick ? 'Cognizer 关系图，点击节点看详情' : 'Cognizer 关系图'}
>
	{#each edges as e}
		{@const a = pos.get(e.a)}
		{@const b = pos.get(e.b)}
		{#if a && b}
			<line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="currentColor" stroke-opacity="0.25" />
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
					<circle r="6" fill="currentColor" />
					<text x="9" y="4" font-size="10" fill="currentColor">{n.label}</text>
				</g>
			{:else}
				<g transform={`translate(${p.x},${p.y})`}>
					<circle r="6" fill="currentColor" />
					<text x="9" y="4" font-size="10" fill="currentColor">{n.label}</text>
				</g>
			{/if}
		{/if}
	{/each}
</svg>
