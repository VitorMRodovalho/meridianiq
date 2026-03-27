// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
import type { Session, User } from '@supabase/supabase-js';
import { writable, derived } from 'svelte/store';
import { supabase } from './supabase';

const REDIRECT_URL =
	(import.meta.env.VITE_REDIRECT_URL as string) ||
	`${typeof window !== 'undefined' ? window.location.origin : 'https://meridianiq.pages.dev'}/auth/callback`;

// ---------------------------------------------------------------------------
// Svelte stores — reactive auth state
// ---------------------------------------------------------------------------

export const user = writable<User | null>(null);
export const session = writable<Session | null>(null);
export const isLoading = writable<boolean>(true);
export const isAuthenticated = derived(user, ($user) => $user !== null);

// ---------------------------------------------------------------------------
// Initialise — call once from the root layout
// ---------------------------------------------------------------------------

export async function initAuth(): Promise<void> {
	// Restore existing session
	const { data } = await supabase.auth.getSession();
	session.set(data.session);
	user.set(data.session?.user ?? null);
	isLoading.set(false);

	// Keep state in sync with Supabase auth events
	supabase.auth.onAuthStateChange((_event, s) => {
		session.set(s);
		user.set(s?.user ?? null);
	});
}

// ---------------------------------------------------------------------------
// Sign-in helpers
// ---------------------------------------------------------------------------

export async function signInWithGoogle(): Promise<void> {
	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'google',
		options: {
			redirectTo: REDIRECT_URL
		}
	});
	if (error) throw error;
}

export async function signInWithAzure(): Promise<void> {
	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'azure',
		options: {
			redirectTo: REDIRECT_URL,
			scopes: 'email'
		}
	});
	if (error) throw error;
}

export async function signOut(): Promise<void> {
	const { error } = await supabase.auth.signOut();
	if (error) throw error;
}
