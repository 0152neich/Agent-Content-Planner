import { createLazyFileRoute } from '@tanstack/react-router';
import { RegisterFeature } from '~features/auth';

export const Route = createLazyFileRoute('/register')({
  component: RegisterFeature,
});
