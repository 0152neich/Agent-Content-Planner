import React, { useRef, useState } from 'react';
import { Box, Button, IconButton, InputAdornment, Link, Paper, TextField, Typography, useTheme } from '@mui/material';
import Visibility from '@mui/icons-material/Visibility';
import VisibilityOff from '@mui/icons-material/VisibilityOff';
import { useNavigate, Link as RouterLink } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import brandLogo from '@/assets/app-logos/brand-logo.png';
import { loginApi, meApi, registerApi } from '../api/authApi';
import { clearAccessToken, setAccessToken } from '../authStorage';

export const RegisterCard: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const navigate = useNavigate();
  const [userName, setUserName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const passwordInputRef = useRef<HTMLInputElement | null>(null);
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const handleRegister = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError(null);

    if (password.trim().length < 8) {
      setError(t('authExtended.register.passwordMin'));
      return;
    }

    setLoading(true);
    const normalizedEmail = email.trim().toLowerCase();
    let created = false;

    try {
      await registerApi({
        user_name: userName.trim(),
        email: normalizedEmail,
        password,
        full_name: fullName.trim() || null,
        phone: phone.trim() || null,
      });
      created = true;

      const loginResult = await loginApi({ identifier: normalizedEmail, password });
      setAccessToken(loginResult.access_token);
      await meApi(loginResult.access_token);
      navigate({ to: '/welcome' });
    } catch (err) {
      clearAccessToken();
      if (created) {
        setError(t('authExtended.register.autoLoginFailed'));
        navigate({ to: '/login' });
        return;
      }
      setError(err instanceof Error ? err.message : t('authExtended.register.failed'));
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
          width: '100%',
          maxWidth: 450,
          borderRadius: 3,
          border: isDark ? '1px solid #263246' : '1px solid #d9e2ec',
          boxShadow: isDark ? '0 22px 50px rgba(0, 0, 0, 0.45)' : '0 22px 50px rgba(25, 66, 108, 0.18)',
          px: { xs: 2, md: 3 },
          py: { xs: 2.4, md: 3 },
          backgroundImage: 'none',
          bgcolor: isDark ? '#0f172a' : '#ffffff',
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2.2 }}>
          <Box
            sx={{
              width: 62,
              height: 62,
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
            fontSize: { xs: '1.7rem', md: '2.1rem' },
            lineHeight: 1.1,
            fontWeight: 800,
            color: isDark ? '#e5eefc' : '#1e293b',
            mb: 1,
          }}
        >
          {t('authExtended.register.createTitle')}
        </Typography>
        <Typography
          sx={{
            textAlign: 'center',
            color: isDark ? '#9fb5d1' : '#6b7280',
            fontSize: '0.98rem',
            mb: 2.2,
          }}
        >
          {t('authExtended.register.subtitle')}
        </Typography>

        <Box component="form" onSubmit={handleRegister} sx={{ display: 'flex', flexDirection: 'column', gap: 1.15 }}>
          <TextField
            fullWidth
            placeholder={t('authExtended.register.usernamePlaceholder')}
            required
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
          />
          <TextField
            fullWidth
            placeholder={t('authExtended.register.emailPlaceholder')}
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextField
            fullWidth
            placeholder={t('authExtended.register.passwordPlaceholder')}
            type={showPassword ? 'text' : 'password'}
            required
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
          <TextField
            fullWidth
            placeholder={t('authExtended.register.fullNamePlaceholder')}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <TextField
            fullWidth
            placeholder={t('authExtended.register.phonePlaceholder')}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />

          <Button
            type="submit"
            variant="contained"
            fullWidth
            sx={{
              mt: 0.9,
              py: 1.05,
              borderRadius: 1.2,
              fontSize: '1rem',
              fontWeight: 800,
            }}
            disabled={loading}
          >
            {loading ? t('authExtended.register.creating') : t('authExtended.register.createButton')}
          </Button>

          {error && (
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          )}
        </Box>

        <Typography sx={{ mt: 1.6, textAlign: 'center', color: isDark ? '#c6d4e6' : '#374151', fontSize: '1rem' }}>
          {t('authExtended.register.haveAccount')}{' '}
          <Link
            component={RouterLink}
            to="/login"
            sx={{ color: isDark ? '#7dd3fc' : '#2f6f90', textDecoration: 'none', fontWeight: 700, '&:hover': { textDecoration: 'underline' } }}
          >
            {t('auth.signIn')}
          </Link>
        </Typography>
      </Paper>
    </Box>
  );
};
