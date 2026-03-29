import type { HandleClientError } from '@sveltejs/kit';

export const handleError: HandleClientError = ({ error, message }) => {
  console.error('[MeridianIQ]', message, error);
  return {
    message: 'An unexpected error occurred. Please try again.',
  };
};
