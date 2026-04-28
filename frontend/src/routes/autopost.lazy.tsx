import { createLazyFileRoute } from '@tanstack/react-router';
import { AutoPostFeature } from '~features/autopost';

export const Route = createLazyFileRoute('/autopost')({
  component: AutoPostFeature,
});
