import { createLazyFileRoute } from '@tanstack/react-router';
import { Outlet, useLocation } from '@tanstack/react-router';
import { AuthFeature } from '~features/auth';

export const Route = createLazyFileRoute('/login')({
  component: LoginRouteComponent,
});

function LoginRouteComponent() {
  const location = useLocation();
  if (location.pathname.startsWith('/login/google-callback')) {
    return <Outlet />;
  }
  return <AuthFeature />;
}
