// MIT License
// Copyright (c) 2026 Vitor Maia Rodovalho
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from './supabase';

// ---------------------------------------------------------------------------
// Svelte 5 runes — reactive auth state
// ---------------------------------------------------------------------------

let _user = $state<User | null>(null);
let _session = $state<Session | null>(null);
let _loading = $state<boolean>(true);

export const auth = {
	get user() {
		return _user;
	},
	get session() {
		return _session;
	},
	get loading() {
		return _loading;
	}
};

// ---------------------------------------------------------------------------
// Initialise — call once from the root layout
// ---------------------------------------------------------------------------

export async function initAuth(): Promise<void> {
	// Restore existing session
	const { data } = await supabase.auth.getSession();
	_session = data.session;
	_user = data.session?.user ?? null;
	_loading = false;

	// Keep state in sync with Supabase auth events
	supabase.auth.onAuthStateChange((_event, session) => {
		_session = session;
		_user = session?.user ?? null;
	});
}

// ---------------------------------------------------------------------------
// Sign-in helpers
// ---------------------------------------------------------------------------

export async function signInWithGoogle(): Promise<void> {
	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'google',
		options: {
			redirectTo: `${window.location.origin}/auth/callback`
		}
	});
	if (error) throw error;
}

export async function signInWithAzure(): Promise<void> {
	const { error } = await supabase.auth.signInWithOAuth({
		provider: 'azure',
		options: {
			redirectTo: `${window.location.origin}/auth/callback`,
			scopes: 'email'
		}
	});
	if (error) throw error;
}

export async function signOut(): Promise<void> {
	const { error } = await supabase.auth.signOut();
	if (error) throw error;
}
