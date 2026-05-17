import { createLazyFileRoute } from '@tanstack/react-router';
import { HistoryFeature } from '~features/history';

export const Route = createLazyFileRoute('/history')({
  component: HistoryFeature,
});
