import { createRootRoute, Outlet, useLocation } from '@tanstack/react-router';
import { AppLayout } from '~components/AppLayout';
import { Box } from '@mui/material';
import { SnackbarProvider } from '@/components/AppLayout/SnackbarContext';

export const Route = createRootRoute({
  component: () => {
    const location = useLocation();
    const isStandalone =
      location.pathname === '/' ||
      location.pathname === '/welcome' ||
      location.pathname === '/login' ||
      location.pathname === '/login/google-callback' ||
      location.pathname === '/register' ||
      location.pathname === '/forgot-password' ||
      location.pathname === '/reset-password' ||
      location.pathname === '/workspace' ||
      location.pathname === '/autopost';

    if (isStandalone) {
      return (
        <SnackbarProvider>
          <Box sx={{ minHeight: '100vh', width: '100vw', bgcolor: 'transparent', overflowX: 'hidden' }}>
            <Outlet />
          </Box>
        </SnackbarProvider>
      );
    }

    return (
      <SnackbarProvider>
        <AppLayout>
          <Outlet />
        </AppLayout>
      </SnackbarProvider>
    );
  },
});
