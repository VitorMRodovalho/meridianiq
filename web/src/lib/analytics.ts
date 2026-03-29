/**
 * Lightweight analytics wrapper.
 * Loads PostHog only if VITE_POSTHOG_KEY is set.
 * All calls are no-ops when PostHog is not configured.
 */

const POSTHOG_KEY = import.meta.env.VITE_POSTHOG_KEY as string | undefined;
const POSTHOG_HOST = (import.meta.env.VITE_POSTHOG_HOST as string) || 'https://us.i.posthog.com';

let posthog: any = null;

export async function initAnalytics(): Promise<void> {
  if (!POSTHOG_KEY || typeof window === 'undefined') return;

  try {
    const mod = await import('posthog-js');
    posthog = mod.default;
    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      capture_pageview: true,
      capture_pageleave: true,
      persistence: 'localStorage',
      autocapture: false, // only track explicit events
    });
  } catch {
    // PostHog unavailable — silently degrade
  }
}

export function trackEvent(event: string, properties?: Record<string, unknown>): void {
  posthog?.capture(event, properties);
}

export function identifyUser(userId: string, traits?: Record<string, unknown>): void {
  posthog?.identify(userId, traits);
}

export function resetUser(): void {
  posthog?.reset();
}
