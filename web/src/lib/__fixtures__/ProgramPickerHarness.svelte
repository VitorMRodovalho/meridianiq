<script lang="ts">
	// Test harness: renders ProgramPicker and shows its bound choice as JSON.
	import ProgramPicker from '$lib/components/ProgramPicker.svelte';
	import type { ProgramChoice, ProgramOption } from '$lib/programPick';

	let {
		programs,
		shortName,
		excludeId = null,
		loading = false
	}: {
		programs: (ProgramOption & { revision_count?: number })[];
		shortName: string | null;
		excludeId?: string | null;
		loading?: boolean;
	} = $props();
	let choice: ProgramChoice | null = $state(null);
</script>

<ProgramPicker {programs} {shortName} {excludeId} {loading} idPrefix="t" bind:choice />
<output data-testid="choice">{JSON.stringify(choice)}</output>
