import React, { useEffect, useMemo, useState } from 'react';
import { Alert, Box, Button, CircularProgress, Paper, Typography, useTheme } from '@mui/material';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';

import { meApi, refreshApi } from '../api/authApi';
import { clearAccessToken, setAccessToken } from '../authStorage';

const mapGoogleError = (code: string | null): string => {
  switch (code) {
    case 'google_oauth_denied':
      return 'Google login was cancelled.';
    case 'google_invalid_state':
      return 'Google login session expired. Please try again.';
    case 'inactive_user':
      return 'Your account is inactive. Please contact support.';
    case 'google_account_conflict':
      return 'Google account conflict detected. Please sign in with password first.';
    case 'google_auth_invalid':
      return 'Google authentication failed. Please try again.';
    default:
      return 'Google login failed. Please try again.';
  }
};

export const GoogleCallbackCard: React.FC = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const search = useMemo(
    () => new URLSearchParams(window.location.search),
    [],
  );

  useEffect(() => {
    const bootstrap = async (): Promise<void> => {
      const status = search.get('status');
      const errorCode = search.get('error');
      if (errorCode) {
        clearAccessToken();
        setError(mapGoogleError(errorCode));
        setLoading(false);
        return;
      }

      if (status !== 'success') {
        clearAccessToken();
        setError(mapGoogleError(null));
        setLoading(false);
        return;
      }

      try {
        const refreshed = await refreshApi();
        setAccessToken(refreshed.access_token);
        await meApi(refreshed.access_token);
        navigate({ to: '/welcome' });
      } catch (err) {
        clearAccessToken();
        setError(err instanceof Error ? err.message : 'Google login failed.');
      } finally {
        setLoading(false);
      }
    };

    void bootstrap();
  }, [navigate, search]);

  return (
    <Box
      sx={{
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        px: 2,
        background:
          isDark
            ? 'radial-gradient(120% 90% at 50% 0%, #0f172a 0%, #0b1324 55%, #060b16 100%)'
            : 'radial-gradient(120% 90% at 50% 0%, #eff7ff 0%, #d7e8f8 55%, #c8def3 100%)',
      }}
    >
      <Paper
        sx={{
          width: '100%',
          maxWidth: 420,
          borderRadius: 2,
          border: isDark ? '1px solid #263246' : '1px solid #d7e0ea',
          boxShadow: isDark ? '0 22px 50px rgba(0, 0, 0, 0.45)' : '0 22px 50px rgba(25, 66, 108, 0.18)',
          px: 3,
          py: 3.5,
          display: 'flex',
          flexDirection: 'column',
          gap: 2,
          alignItems: 'center',
        }}
      >
        {loading ? (
          <>
            <CircularProgress size={30} />
            <Typography sx={{ fontWeight: 700, color: isDark ? '#e5eefc' : '#0f1f47' }}>
              Completing Google sign-in...
            </Typography>
          </>
        ) : (
          <>
            <Typography sx={{ fontSize: '1.35rem', fontWeight: 800, color: isDark ? '#e5eefc' : '#0f1f47' }}>
              Google Sign-in
            </Typography>
            <Alert severity="error" sx={{ width: '100%' }}>
              {error || 'Google login failed.'}
            </Alert>
            <Button component={RouterLink} to="/login" variant="contained" fullWidth>
              Back to Sign In
            </Button>
          </>
        )}
      </Paper>
    </Box>
  );
};
