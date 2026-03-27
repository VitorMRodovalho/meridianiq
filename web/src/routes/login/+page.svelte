<script lang="ts">
	import { signInWithGoogle, signInWithAzure } from '$lib/auth';

	let error = $state('');
	let loading = $state(false);

	async function handleGoogle() {
		loading = true;
		error = '';
		try {
			await signInWithGoogle();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Sign-in failed';
			loading = false;
		}
	}

	async function handleMicrosoft() {
		loading = true;
		error = '';
		try {
			await signInWithAzure();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Sign-in failed';
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Sign In — MeridianIQ</title>
</svelte:head>

<div class="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
	<div class="sm:mx-auto sm:w-full sm:max-w-md">
		<h1 class="text-center text-3xl font-bold tracking-tight text-gray-900">MeridianIQ</h1>
		<p class="mt-2 text-center text-sm text-gray-500">Schedule Intelligence Platform</p>
	</div>

	<div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
		<div class="bg-white py-8 px-4 shadow rounded-lg sm:px-10 space-y-4">
			<h2 class="text-xl font-semibold text-gray-800 text-center">Sign in to your account</h2>

			{#if error}
				<div class="rounded-md bg-red-50 p-3 text-sm text-red-700 border border-red-200">
					{error}
				</div>
			{/if}

			<!-- Google -->
			<button
				onclick={handleGoogle}
				disabled={loading}
				class="w-full flex items-center justify-center gap-3 rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
			>
				<!-- Google icon -->
				<svg class="w-5 h-5" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
					<path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
					<path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
					<path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
					<path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
				</svg>
				Continue with Google
			</button>

			<!-- Microsoft -->
			<button
				onclick={handleMicrosoft}
				disabled={loading}
				class="w-full flex items-center justify-center gap-3 rounded-md border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
			>
				<!-- Microsoft icon -->
				<svg class="w-5 h-5" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg">
					<rect x="1" y="1" width="10" height="10" fill="#f25022"/>
					<rect x="12" y="1" width="10" height="10" fill="#00a4ef"/>
					<rect x="1" y="12" width="10" height="10" fill="#7fba00"/>
					<rect x="12" y="12" width="10" height="10" fill="#ffb900"/>
				</svg>
				Continue with Microsoft
			</button>

			<p class="text-center text-xs text-gray-400 pt-2">
				By signing in you agree to the MeridianIQ terms of service.
			</p>
		</div>
	</div>
</div>
