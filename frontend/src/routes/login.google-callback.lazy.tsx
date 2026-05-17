import { createLazyFileRoute } from '@tanstack/react-router';
import { GoogleCallbackFeature } from '~features/auth';

export const Route = createLazyFileRoute('/login/google-callback')({
  component: GoogleCallbackFeature,
});
