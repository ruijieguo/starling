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
