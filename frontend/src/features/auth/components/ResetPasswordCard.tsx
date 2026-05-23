import React, { useEffect, useRef, useState } from 'react';
import { Box, Paper, TextField, Button, Typography, Link, Alert, IconButton, InputAdornment } from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import { KeyRound } from 'lucide-react';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { AuthHeaderIcon } from './AuthHeaderIcon';
import { forgotPasswordResetApi } from '../api/authApi';

const RESET_SESSION_KEY = 'password_reset_verified_email';
const RESET_TOKEN_SESSION_KEY = 'password_reset_token';

export const ResetPasswordCard: React.FC = () => {
  const { t } = useTranslation();
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const confirmPasswordInputRef = useRef<HTMLInputElement | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');
  const [resetToken, setResetToken] = useState('');
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

  const toggleConfirmPasswordVisibility = (): void => {
    const input = confirmPasswordInputRef.current;
    const start = input?.selectionStart ?? null;
    const end = input?.selectionEnd ?? null;
    setShowConfirmPassword((prev) => !prev);
    requestAnimationFrame(() => {
      const nextInput = confirmPasswordInputRef.current;
      if (!nextInput) return;
      nextInput.focus();
      if (start !== null && end !== null) {
        nextInput.setSelectionRange(start, end);
      }
    });
  };

  useEffect(() => {
    const verifiedEmail = sessionStorage.getItem(RESET_SESSION_KEY);
    const token = sessionStorage.getItem(RESET_TOKEN_SESSION_KEY);
    if (!verifiedEmail || !token) {
      navigate({ to: '/forgot-password' });
      return;
    }
    setEmail(verifiedEmail);
    setResetToken(token);
  }, [navigate]);

  const handleResetPassword = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError(t('authExtended.reset.passwordMin'));
      return;
    }

    if (password !== confirmPassword) {
      setError(t('authExtended.reset.confirmMismatch'));
      return;
    }

    setLoading(true);
    try {
      await forgotPasswordResetApi(resetToken, password);
      setDone(true);
      sessionStorage.removeItem(RESET_SESSION_KEY);
      sessionStorage.removeItem(RESET_TOKEN_SESSION_KEY);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('authExtended.reset.failed'));
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
        alignItems: { xs: 'flex-start', sm: 'center' },
        py: { xs: 4, sm: 0 },
        px: 2,
      }}
    >
      <Box sx={{ width: '100%', maxWidth: 460, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <AuthHeaderIcon icon={KeyRound} />

        <Typography variant="h3" sx={{ fontSize: { xs: '1.9rem', md: '2.2rem' }, fontWeight: 700, mb: 1, textAlign: 'center' }}>
          {t('authExtended.reset.title')}
        </Typography>
        <Typography variant="h6" color="text.secondary" sx={{ fontWeight: 400, mb: 3, textAlign: 'center' }}>
          {t('authExtended.reset.subtitle', { email: email || t('authExtended.reset.yourAccount') })}
        </Typography>

        <Box sx={{ width: '100%', display: 'flex', gap: 1, mb: 2 }}>
          <Box sx={{ flex: 1, height: 4, borderRadius: 999, bgcolor: 'primary.main', opacity: 0.9 }} />
          <Box sx={{ flex: 1, height: 4, borderRadius: 999, bgcolor: 'primary.main', opacity: 0.9 }} />
          <Box sx={{ flex: 1, height: 4, borderRadius: 999, bgcolor: 'primary.main', opacity: 0.9 }} />
        </Box>

        <Paper sx={{ width: '100%', p: { xs: 2.5, md: 4 }, borderRadius: 5 }}>
          {!done ? (
            <Box component="form" onSubmit={handleResetPassword} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              <Box>
                <Typography variant="body1" sx={{ mb: 1 }}>
                  {t('authExtended.reset.newPassword')}
                </Typography>
                <TextField
                  fullWidth
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder={t('authExtended.reset.newPasswordPlaceholder')}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
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

              <Box>
                <Typography variant="body1" sx={{ mb: 1 }}>
                  {t('authExtended.reset.confirmPassword')}
                </Typography>
                <TextField
                  fullWidth
                  type={showConfirmPassword ? 'text' : 'password'}
                  required
                  placeholder={t('authExtended.reset.confirmPasswordPlaceholder')}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  inputRef={confirmPasswordInputRef}
                  InputProps={{
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          aria-label={showConfirmPassword ? t('authExtended.password.hide') : t('authExtended.password.show')}
                          onClick={toggleConfirmPasswordVisibility}
                          onMouseDown={(event) => event.preventDefault()}
                          edge="end"
                        >
                          {showConfirmPassword ? <VisibilityOff /> : <Visibility />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
              </Box>

              {error && <Alert severity="error">{error}</Alert>}

              <Button type="submit" variant="contained" fullWidth sx={{ py: 1.35, fontSize: '1rem', fontWeight: 700 }} disabled={loading}>
                {loading ? t('authExtended.reset.updating') : t('authExtended.reset.updateButton')}
              </Button>
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Alert severity="success">{t('authExtended.reset.success')}</Alert>
              <Button component={RouterLink} to="/login" variant="contained" fullWidth sx={{ py: 1.35, fontWeight: 700 }}>
                {t('authExtended.reset.goToSignIn')}
              </Button>
            </Box>
          )}
        </Paper>

        {!done && (
          <Typography variant="body1" color="text.secondary" sx={{ mt: 3, textAlign: 'center' }}>
            {t('authExtended.reset.backTo')}{' '}
            <Link
              component={RouterLink}
              to="/login"
              sx={{ color: 'primary.main', textDecoration: 'none', fontWeight: 600, '&:hover': { textDecoration: 'underline' } }}
            >
              {t('auth.signIn')}
            </Link>
          </Typography>
        )}
      </Box>
    </Box>
  );
};
