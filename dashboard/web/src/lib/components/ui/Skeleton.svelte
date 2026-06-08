<script lang="ts">
	let { class: klass = 'h-4 w-full' }: { class?: string } = $props();
</script>

<div class="animate-pulse rounded-md bg-border/60 {klass}" aria-hidden="true"></div>
