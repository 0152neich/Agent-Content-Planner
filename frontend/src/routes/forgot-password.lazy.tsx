import { createLazyFileRoute } from '@tanstack/react-router';
import { ForgotPasswordFeature } from '~features/auth';

export const Route = createLazyFileRoute('/forgot-password')({
  component: ForgotPasswordFeature,
});
