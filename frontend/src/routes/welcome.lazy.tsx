import { createLazyFileRoute } from '@tanstack/react-router';
import WelcomeFeature from '~features/workspace/components/WelcomeFeature';

export const Route = createLazyFileRoute('/welcome')({
  component: WelcomeFeature,
});
