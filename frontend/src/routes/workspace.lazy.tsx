import { createLazyFileRoute } from '@tanstack/react-router';
import { WorkspaceFeature } from '~features/workspace';

export const Route = createLazyFileRoute('/workspace')({
  component: WorkspaceFeature,
});
