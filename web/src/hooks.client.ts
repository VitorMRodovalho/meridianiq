import type { HandleClientError } from '@sveltejs/kit/hooks';

// SvelteKit 3 passes every error here, 404s included, as `{ kind, error }`.
// The error page picks its copy from the status alone, so every message is
// replaced with a generic one and no internals reach the UI.
export const handleError: HandleClientError = ({ kind, error }) => {
  console.error('[MeridianIQ]', kind, error);
  return {
    message: 'An unexpected error occurred. Please try again.',
  };
};
