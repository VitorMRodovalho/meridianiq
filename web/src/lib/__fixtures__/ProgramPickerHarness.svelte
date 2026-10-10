<script lang="ts">
	// Test harness: renders ProgramPicker and shows its bound choice as JSON.
	import ProgramPicker from '$lib/components/ProgramPicker.svelte';
	import type { ProgramChoice, ProgramOption } from '$lib/programPick';

	let {
		programs,
		shortName,
		excludeId = null
	}: { programs: ProgramOption[]; shortName: string | null; excludeId?: string | null } = $props();
	let choice: ProgramChoice | null = $state(null);
</script>

<ProgramPicker {programs} {shortName} {excludeId} idPrefix="t" bind:choice />
<output data-testid="choice">{JSON.stringify(choice)}</output>
