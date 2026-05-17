import React, { useEffect, useMemo, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { CssBaseline, ThemeProvider } from '@mui/material';
import type { PaletteMode } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { routeTree } from './routeTree.gen';
import { ColorModeContext } from './theme/colorMode';
import { getAppTheme } from './theme/theme';
import { ensureAuthenticatedAccessToken } from './features/auth/api/authApi';
import { clearAccessToken, getAccessToken } from './features/auth/authStorage';
import './i18n';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: 'intent',
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}

const getInitialMode = (): PaletteMode => {
  const stored = localStorage.getItem('app-color-mode');
  if (stored === 'light') return 'light';
  return 'light';
};

const App = () => {
  const [mode, setMode] = useState<PaletteMode>(getInitialMode);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;

    let active = true;
    const bootstrap = async () => {
      const refreshedToken = await ensureAuthenticatedAccessToken();
      if (!refreshedToken && active) {
        clearAccessToken();
      }
    };

    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const colorModeValue = useMemo(
    () => ({
      mode,
      toggleMode: () => {
        setMode((prev) => {
          const next = prev === 'dark' ? 'light' : 'dark';
          localStorage.setItem('app-color-mode', next);
          return next;
        });
      },
    }),
    [mode],
  );

  const theme = useMemo(() => getAppTheme(mode), [mode]);

  return (
    <QueryClientProvider client={queryClient}>
      <ColorModeContext.Provider value={colorModeValue}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <RouterProvider router={router} />
        </ThemeProvider>
      </ColorModeContext.Provider>
    </QueryClientProvider>
  );
};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
