import React, { useRef, useState } from 'react';
import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  IconButton,
  InputAdornment,
  Link,
  Paper,
  TextField,
  Typography,
  useTheme,
} from '@mui/material';
import GoogleIcon from '@mui/icons-material/Google';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import { useNavigate, Link as RouterLink } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import brandLogo from '@/assets/app-logos/brand-logo.png';
import { loginApi, meApi, startGoogleLogin } from '../api/authApi';
import {
  clearAccessToken,
  clearRememberedIdentifier,
  getRememberedIdentifier,
  setAccessToken,
  setRememberedIdentifier,
} from '../authStorage';

export const LoginCard: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const initialRememberedIdentifier = getRememberedIdentifier();
  const [identifier, setIdentifier] = useState(initialRememberedIdentifier ?? '');
  const [rememberAccount, setRememberAccount] = useState(Boolean(initialRememberedIdentifier));
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const togglePasswordVisibility = (): void => {
    const input = passwordInputRef.current;
    const start = input?.selectionStart ?? null;
    const end = input?.selectionEnd ?? null;
    setShowPassword((prev) => !prev);
    requestAnimationFrame(() => {
      const nextInput = passwordInputRef.current;
      if (!nextInput) return;
      nextInput.focus();
      if (start !== null && end !== null) {
        nextInput.setSelectionRange(start, end);
      }
    });
  };

  const handleLogin = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);
    const normalizedIdentifier = identifier.trim();
    if (!normalizedIdentifier) {
      setError(t('authExtended.login.identifierRequired'));
      return;
    }
    setLoading(true);

    try {
      const result = await loginApi({ identifier: normalizedIdentifier, password });
      if (rememberAccount) {
        setRememberedIdentifier(normalizedIdentifier);
      } else {
        clearRememberedIdentifier();
      }
      setAccessToken(result.access_token);
      await meApi(result.access_token);
      navigate({ to: '/welcome' });
    } catch (err) {
      clearAccessToken();
      setError(err instanceof Error ? err.message : t('authExtended.login.failed'));
    } finally {
      setLoading(false);
    }
  };

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
          position: 'relative',
          width: '100%',
          maxWidth: 440,
          borderRadius: 3,
          border: isDark ? '1px solid #263246' : '1px solid #d7e0ea',
          boxShadow: isDark ? '0 22px 50px rgba(0, 0, 0, 0.45)' : '0 22px 50px rgba(25, 66, 108, 0.18)',
          overflow: 'hidden',
          backgroundImage: 'none',
          bgcolor: isDark ? '#0f172a' : '#ffffff',
        }}
      >
        <Box sx={{ px: { xs: 2, md: 3 }, py: { xs: 2.4, md: 3 } }}>
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2.6 }}>
            <Box
              sx={{
                width: 64,
                height: 64,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Box
                component="img"
                src={brandLogo}
                alt={t('authExtended.brandLogoAlt')}
                sx={{ width: 56, height: 56, objectFit: 'contain' }}
              />
            </Box>
          </Box>

          <Typography
            sx={{
              textAlign: 'center',
              fontSize: { xs: '1.8rem', md: '2.2rem' },
              lineHeight: 1.1,
              fontWeight: 800,
              color: isDark ? '#e5eefc' : '#0f1f47',
              mb: 2.2,
            }}
          >
            {t('auth.welcome')}
          </Typography>

          <Box component="form" onSubmit={handleLogin} sx={{ display: 'flex', flexDirection: 'column', gap: 1.9 }}>
            <Box>
              <Typography sx={{ mb: 0.8, color: isDark ? '#dbe7f8' : '#0f172a', fontWeight: 700, fontSize: '1.05rem' }}>
                {t('authExtended.login.identifierLabel')}
              </Typography>
              <TextField
                fullWidth
                placeholder={t('authExtended.login.identifierPlaceholder')}
                type="text"
                required
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoComplete="username"
              />
            </Box>

            <Box>
              <Box sx={{ mb: 0.8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ color: isDark ? '#dbe7f8' : '#0f172a', fontWeight: 700, fontSize: '1.05rem' }}>
                  {t('auth.passwordLabel')}
                </Typography>
                <Link
                  component={RouterLink}
                  to="/forgot-password"
                  sx={{
                    color: isDark ? '#7dd3fc' : '#2f6a86',
                    textDecoration: 'none',
                    fontWeight: 600,
                    '&:hover': { textDecoration: 'underline' },
                  }}
                >
                  {t('auth.forgotPassword')}
                </Link>
              </Box>
              <TextField
                fullWidth
                placeholder="••••••••"
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={rememberAccount ? 'current-password' : 'off'}
                inputRef={passwordInputRef}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        aria-label={showPassword ? t('authExtended.password.hide') : t('authExtended.password.show')}
                        onClick={togglePasswordVisibility}
                        onMouseDown={(event) => event.preventDefault()}
                        edge="end"
                      >
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </Box>

            <FormControlLabel
              control={
                <Checkbox
                  checked={rememberAccount}
                  onChange={(event) => setRememberAccount(event.target.checked)}
                  sx={{ py: 0.4 }}
                />
              }
              label={
                <Typography sx={{ fontSize: '0.92rem', color: isDark ? '#9fb5d1' : '#334155', fontWeight: 600 }}>
                  {t('authExtended.login.rememberAccount')}
                </Typography>
              }
              sx={{ ml: 0, mr: 0 }}
            />

            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={loading}
              sx={{
                mt: 0.8,
                py: 1.05,
                fontSize: '1rem',
                fontWeight: 800,
                borderRadius: 1.2,
              }}
            >
              {loading ? t('auth.signingIn') : t('auth.signIn')}
            </Button>

            {error && (
              <Typography variant="body2" color="error">
                {error}
              </Typography>
            )}

            <Box sx={{ display: 'flex', alignItems: 'center', color: isDark ? '#8ea5c2' : '#475569', pt: 1.1 }}>
              <Box sx={{ flex: 1, height: 1, bgcolor: isDark ? '#2b3a51' : '#d6deea' }} />
              <Typography sx={{ px: 1.7, fontSize: '0.9rem', fontWeight: 500 }}>
                {t('auth.orContinue')}
              </Typography>
              <Box sx={{ flex: 1, height: 1, bgcolor: isDark ? '#2b3a51' : '#d6deea' }} />
            </Box>

            <Button
              variant="outlined"
              fullWidth
              startIcon={<GoogleIcon sx={{ fontSize: 20 }} />}
              onClick={startGoogleLogin}
              sx={{
                py: 1,
                fontWeight: 700,
                fontSize: '0.95rem',
                borderRadius: 1.2,
                borderColor: isDark ? '#3a607f' : '#2f6f90',
                color: isDark ? '#e6f4ff' : '#2b6588',
                bgcolor: isDark ? '#101b2c' : '#fbfdff',
              }}
            >
              {t('auth.googleLogin')}
            </Button>
          </Box>
        </Box>

        <Box
          sx={{
            borderTop: '1px solid #e2e8f0',
            px: 3,
            py: 1.6,
            textAlign: 'center',
            bgcolor: isDark ? '#0c1525' : '#fbfcff',
          }}
        >
          <Typography sx={{ color: isDark ? '#d4deed' : '#1f2937', fontSize: '1rem' }}>
            {t('auth.noAccount')}{' '}
            <Link
              component={RouterLink}
              to="/register"
              sx={{
                color: isDark ? '#7dd3fc' : '#2f6f90',
                textDecoration: 'none',
                fontWeight: 700,
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              {t('authExtended.login.signUp')}
            </Link>
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};
