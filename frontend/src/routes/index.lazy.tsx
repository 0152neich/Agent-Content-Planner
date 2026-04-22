import { createLazyFileRoute } from '@tanstack/react-router';
import { LandingFeature } from '~features/landing';

export const Route = createLazyFileRoute('/')({
  component: LandingFeature,
});
