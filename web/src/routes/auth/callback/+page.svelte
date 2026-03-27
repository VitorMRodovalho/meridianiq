<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { supabase } from '$lib/supabase';

	onMount(async () => {
		// Supabase exchanges the auth code from the URL hash automatically.
		// Wait briefly for the session to be established, then redirect home.
		const { data, error } = await supabase.auth.getSession();
		if (error) {
			console.error('Auth callback error:', error.message);
			goto('/login');
		} else if (data.session) {
			goto('/');
		} else {
			// Session not yet set — listen for it once
			const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
				listener.subscription.unsubscribe();
				if (session) {
					goto('/');
				} else {
					goto('/login');
				}
			});
		}
	});
</script>

<div class="min-h-screen bg-gray-50 flex items-center justify-center">
	<div class="text-center">
		<div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-indigo-600 border-r-transparent"></div>
		<p class="mt-4 text-sm text-gray-500">Completing sign-in…</p>
	</div>
</div>
