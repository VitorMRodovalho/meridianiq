// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
import { writable, derived } from 'svelte/store';
import type { User, Session } from '@supabase/supabase-js';

// Stores
export const user = writable<User | null>(null);
export const session = writable<Session | null>(null);
export const isAuthenticated = derived(user, ($user) => $user !== null);
export const isLoading = writable(true);

// Lazy init flag — prevents double initialization
let _initialized = false;

/**
 * Initialize auth state. Call this from the root layout's onMount().
 * Uses dynamic import to break circular dependency with supabase.ts.
 */
export async function initAuth() {
	if (_initialized) return;
	_initialized = true;

	const { supabase } = await import('./supabase');

	// Get initial session
	const {
		data: { session: s }
	} = await supabase.auth.getSession();
	session.set(s);
	user.set(s?.user ?? null);
	isLoading.set(false);

	// Listen for auth changes
	supabase.auth.onAuthStateChange((_event, s) => {
		session.set(s);
		user.set(s?.user ?? null);
		isLoading.set(false);
	});
}

// Auth actions — all use dynamic import
export async function signInWithGoogle() {
	const { supabase } = await import('./supabase');
	const redirectUrl =
		(import.meta.env.VITE_REDIRECT_URL as string) ||
		`${window.location.origin}/auth/callback`;

	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'google',
		options: { redirectTo: redirectUrl }
	});
	if (error) throw error;
}

export async function signInWithAzure() {
	const { supabase } = await import('./supabase');
	const redirectUrl =
		(import.meta.env.VITE_REDIRECT_URL as string) ||
		`${window.location.origin}/auth/callback`;

	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'azure',
		options: { redirectTo: redirectUrl, scopes: 'email profile openid' }
	});
	if (error) throw error;
}

export async function signInWithLinkedIn() {
	const { supabase } = await import('./supabase');
	const redirectUrl =
		(import.meta.env.VITE_REDIRECT_URL as string) ||
		`${window.location.origin}/auth/callback`;

	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'linkedin_oidc',
		options: { redirectTo: redirectUrl }
	});
	if (error) throw error;
}

export async function signOut() {
	const { supabase } = await import('./supabase');
	const { error } = await supabase.auth.signOut();
	if (error) throw error;
}
