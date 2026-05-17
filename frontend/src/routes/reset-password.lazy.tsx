import { createLazyFileRoute } from '@tanstack/react-router';
import { ResetPasswordFeature } from '~features/auth';

export const Route = createLazyFileRoute('/reset-password')({
  component: ResetPasswordFeature,
});
