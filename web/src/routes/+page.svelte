<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { getProjects } from '$lib/api';
	import { isAuthenticated, isLoading as authLoading } from '$lib/auth';
	import type { ProjectListItem } from '$lib/types';

	let projects: ProjectListItem[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let authenticated = $state(false);

	onMount(async () => {
		// Wait for auth to initialize
		const unsub = authLoading.subscribe((val) => {
			if (!val) {
				authenticated = get(isAuthenticated);
				if (authenticated) {
					loadProjects();
				} else {
					loading = false;
				}
				unsub();
			}
		});
	});

	async function loadProjects() {
		try {
			const res = await getProjects();
			projects = res.projects;
		} catch (e: unknown) {
			// Silently handle — user may not be authenticated
			error = '';
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>MeridianIQ</title>
</svelte:head>

<div class="p-8 max-w-6xl mx-auto">
	<div class="mb-10">
		<h1 class="text-3xl font-bold text-gray-900">MeridianIQ — Schedule Intelligence Platform</h1>
		<p class="mt-2 text-lg text-gray-600">
			Open-source Primavera P6 schedule validation, comparison, and forensic analysis
		</p>
	</div>

	{#if !authenticated && !loading}
		<div class="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-10">
			<h2 class="text-lg font-semibold text-blue-900 mb-2">Welcome to MeridianIQ</h2>
			<p class="text-sm text-blue-700 mb-4">Sign in to upload and analyze your Primavera P6 schedules. Your data is private and encrypted.</p>
			<a href="/login" class="inline-block bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 transition-colors">Sign in to get started</a>
		</div>
	{/if}

	<!-- Action Cards -->
	<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
		<a
			href="/upload"
			class="block bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md hover:border-blue-300 transition-all"
		>
			<div class="flex items-center gap-4">
				<div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
					<svg class="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
					</svg>
				</div>
				<div>
					<h2 class="text-lg font-semibold text-gray-900">Upload XER File</h2>
					<p class="text-sm text-gray-500">Parse and analyze a Primavera P6 schedule export</p>
				</div>
			</div>
		</a>
		<a
			href="/compare"
			class="block bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md hover:border-blue-300 transition-all"
		>
			<div class="flex items-center gap-4">
				<div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
					<svg class="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
					</svg>
				</div>
				<div>
					<h2 class="text-lg font-semibold text-gray-900">Compare Schedules</h2>
					<p class="text-sm text-gray-500">Detect changes and manipulation between schedule versions</p>
				</div>
			</div>
		</a>
	</div>

	<!-- Project Summary -->
	{#if loading}
		<div class="flex items-center gap-2 text-gray-500">
			<svg class="animate-spin h-5 w-5" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" />
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
			</svg>
			Loading projects...
		</div>
	{:else if error}
		<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
			Could not connect to backend: {error}
		</div>
	{:else if projects.length > 0}
		<div class="bg-white rounded-lg border border-gray-200 p-6">
			<h2 class="text-lg font-semibold text-gray-900 mb-4">Uploaded Projects</h2>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each projects as project}
					<a
						href="/projects/{project.project_id}"
						class="block border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition-all"
					>
						<h3 class="font-medium text-gray-900 truncate">{project.name || project.project_id}</h3>
						<div class="mt-2 flex gap-4 text-sm text-gray-500">
							<span>{project.activity_count} activities</span>
							<span>{project.relationship_count} relationships</span>
						</div>
					</a>
				{/each}
			</div>
		</div>
	{:else}
		<div class="bg-white rounded-lg border border-gray-200 p-6 text-center text-gray-500">
			<p>No projects uploaded yet. Start by uploading an XER file.</p>
		</div>
	{/if}
</div>
