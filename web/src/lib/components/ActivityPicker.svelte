<script lang="ts">
	import { searchActivities } from '$lib/api';

	interface ActivityEntry {
		task_code: string;
		task_name: string;
		task_type?: string;
		wbs_id?: string;
		status_code?: string;
	}

	let {
		projectId,
		selected = $bindable<ActivityEntry[]>([]),
		placeholder = 'Search activity code or name…',
		onchange
	}: {
		projectId: string;
		selected: ActivityEntry[];
		placeholder?: string;
		onchange?: (selected: ActivityEntry[]) => void;
	} = $props();

	let query = $state('');
	let results = $state<ActivityEntry[]>([]);
	let loading = $state(false);
	let showDropdown = $state(false);
	let debounceTimer: ReturnType<typeof setTimeout>;
	let inputEl: HTMLInputElement;

	function handleInput(e: Event) {
		query = (e.target as HTMLInputElement).value;
		clearTimeout(debounceTimer);
		if (query.length < 2) {
			results = [];
			showDropdown = false;
			return;
		}
		showDropdown = true;
		debounceTimer = setTimeout(() => search(query), 300);
	}

	async function search(q: string) {
		if (!q || q.length < 2) {
			results = [];
			return;
		}
		loading = true;
		try {
			const data = await searchActivities(projectId, q, 20);
			results = data.activities;
		} catch {
			results = [];
		} finally {
			loading = false;
		}
	}

	function selectActivity(act: ActivityEntry) {
		if (!selected.find((a) => a.task_code === act.task_code)) {
			selected = [...selected, act];
			onchange?.(selected);
		}
		query = '';
		results = [];
		showDropdown = false;
		inputEl?.focus();
	}

	function removeActivity(code: string) {
		selected = selected.filter((a) => a.task_code !== code);
		onchange?.(selected);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			showDropdown = false;
			results = [];
		}
	}

	function handleBlur() {
		// Delay close to allow click on dropdown item to register
		setTimeout(() => {
			showDropdown = false;
		}, 150);
	}
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="relative" onkeydown={handleKeydown}>
	<!-- Selected chips -->
	{#if selected.length > 0}
		<div class="flex flex-wrap gap-1.5 mb-2">
			{#each selected as act}
				<span
					class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-teal-100 text-teal-800 border border-teal-200"
				>
					<span class="font-mono">{act.task_code}</span>
					{#if act.task_name}
						<span class="text-teal-600 max-w-[140px] truncate">{act.task_name}</span>
					{/if}
					<button
						type="button"
						onclick={() => removeActivity(act.task_code)}
						class="ml-0.5 text-teal-500 hover:text-teal-800 leading-none"
						aria-label="Remove {act.task_code}"
					>
						&times;
					</button>
				</span>
			{/each}
		</div>
	{/if}

	<!-- Search input -->
	<div class="relative">
		<input
			bind:this={inputEl}
			type="text"
			value={query}
			oninput={handleInput}
			onblur={handleBlur}
			onfocus={() => { if (query.length >= 2) showDropdown = true; }}
			{placeholder}
			class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 pr-8"
			autocomplete="off"
		/>
		{#if loading}
			<div class="absolute right-2 top-1/2 -translate-y-1/2">
				<svg class="animate-spin h-4 w-4 text-gray-400" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
				</svg>
			</div>
		{/if}
	</div>

	<!-- Dropdown results -->
	{#if showDropdown && results.length > 0}
		<div
			class="absolute z-20 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto"
		>
			{#each results as act}
				<button
					type="button"
					class="w-full text-left px-3 py-2 hover:bg-teal-50 flex items-start gap-2 border-b border-gray-50 last:border-b-0 focus:outline-none focus:bg-teal-50"
					onmousedown={() => selectActivity(act)}
				>
					<span class="font-mono text-xs text-teal-700 bg-teal-50 border border-teal-100 rounded px-1.5 py-0.5 shrink-0 mt-0.5">
						{act.task_code}
					</span>
					<div class="min-w-0">
						<p class="text-sm text-gray-800 truncate">{act.task_name || '—'}</p>
						{#if act.wbs_id}
							<p class="text-xs text-gray-400 truncate">WBS: {act.wbs_id}</p>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	{:else if showDropdown && !loading && query.length >= 2}
		<div
			class="absolute z-20 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm text-gray-400"
		>
			No activities found for "{query}"
		</div>
	{/if}
</div>
