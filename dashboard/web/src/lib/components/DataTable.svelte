<script lang="ts">
	let { rows, columns }: { rows: Record<string, unknown>[]; columns: string[] } = $props();
</script>

<div class="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
	<table class="w-full text-sm">
		<thead class="bg-zinc-100 dark:bg-zinc-900 text-left">
			<tr>
				{#each columns as c}<th class="px-3 py-2 font-medium text-zinc-500">{c}</th>{/each}
			</tr>
		</thead>
		<tbody>
			{#each rows as r}
				<tr class="border-t border-zinc-100 dark:border-zinc-800">
					{#each columns as c}<td class="px-3 py-1.5">{r[c] ?? ''}</td>{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>
