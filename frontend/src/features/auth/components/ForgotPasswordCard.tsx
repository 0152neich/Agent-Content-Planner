import React, { useEffect, useMemo, useState } from 'react';
import { Box, Paper, TextField, Button, Typography, Link, Alert, useTheme } from '@mui/material';
import { ShieldCheck } from 'lucide-react';
import { Link as RouterLink, useNavigate } from '@tanstack/react-router';
import { forgotPasswordSendOtpApi, forgotPasswordVerifyOtpApi } from '../api/authApi';

const OTP_LENGTH = 6;
const OTP_RESEND_SECONDS = 90;
const RESET_SESSION_KEY = 'password_reset_verified_email';
const RESET_TOKEN_SESSION_KEY = 'password_reset_token';

export const ForgotPasswordCard: React.FC = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [step, setStep] = useState<1 | 2>(1);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendSeconds, setResendSeconds] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = setInterval(() => setResendSeconds((prev) => prev - 1), 1000);
    return () => clearInterval(timer);
  }, [resendSeconds]);

  const otpHelperText = useMemo(() => {
    if (step !== 2) return '';
    if (otp.length === 0) return `Enter ${OTP_LENGTH}-digit OTP sent to your email`;
    return otp.length < OTP_LENGTH ? `OTP must have ${OTP_LENGTH} digits` : '';
  }, [otp.length, step]);

  const handleSendOtp = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError('');
    setNotice('');
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail) {
      setError('Email is required.');
      return;
    }

    setLoading(true);
    try {
      const result = await forgotPasswordSendOtpApi(normalizedEmail);
      setEmail(normalizedEmail);
      setStep(2);
      setResendSeconds(OTP_RESEND_SECONDS);
      const expiresInMinutes = Math.max(Math.floor((result.expires_in ?? 0) / 60), 1);
      setNotice(`OTP has been sent. It will expire in about ${expiresInMinutes} minutes.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send OTP.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault();
    setError('');

    if (otp.length !== OTP_LENGTH) {
      setError(`OTP must have exactly ${OTP_LENGTH} digits.`);
      return;
    }

    setLoading(true);
    try {
      const verifyResult = await forgotPasswordVerifyOtpApi(email, otp);
      sessionStorage.setItem(RESET_SESSION_KEY, email);
      sessionStorage.setItem(RESET_TOKEN_SESSION_KEY, verifyResult.reset_token);
      navigate({ to: '/reset-password' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'OTP verification failed.');
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
      <Box sx={{ width: '100%', maxWidth: 560, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Box
          sx={{
            width: 92,
            height: 92,
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: isDark ? '#66c6ff' : '#1784d3',
            bgcolor: isDark ? '#122236' : '#ddf0ff',
            border: isDark ? '1px solid #2f5b7a' : '1px solid #b8dcf9',
            boxShadow: isDark ? '0 0 0 14px rgba(35, 79, 117, 0.22), 0 16px 40px rgba(0, 0, 0, 0.45)' : '0 0 0 14px rgba(81, 170, 235, 0.16), 0 16px 40px rgba(55, 126, 187, 0.28)',
            mb: 2.8,
          }}
        >
          <ShieldCheck size={44} />
        </Box>

        <Typography
          sx={{
            fontSize: { xs: '2.15rem', md: '3rem' },
            lineHeight: 1.1,
            fontWeight: 800,
            color: isDark ? '#e5eefc' : '#1c2b47',
            textAlign: 'center',
            mb: 1,
          }}
        >
          Recover Your Account
        </Typography>
        <Typography sx={{ color: isDark ? '#c9d9ec' : '#1e293b', textAlign: 'center', fontSize: { xs: '1.05rem', md: '1.15rem' }, mb: 2.8 }}>
          Verify your identity and reset your password
        </Typography>

        <Box sx={{ width: '100%', maxWidth: 480, display: 'flex', gap: 0.8, mb: 2.2 }}>
          <Box sx={{ flex: 1, height: 5, borderRadius: 1, bgcolor: step >= 1 ? '#1e89d8' : isDark ? '#2b3a51' : '#c8d5e4' }} />
          <Box sx={{ flex: 1, height: 5, borderRadius: 1, bgcolor: step >= 2 ? '#1e89d8' : isDark ? '#2b3a51' : '#c8d5e4' }} />
          <Box sx={{ flex: 1, height: 5, borderRadius: 1, bgcolor: isDark ? '#2b3a51' : '#c8d5e4' }} />
        </Box>

        <Paper
          sx={{
            width: '100%',
            maxWidth: 480,
            p: { xs: 2.4, md: 3 },
            borderRadius: 3,
            border: isDark ? '1px solid #263246' : '1px solid #d8e2ee',
            backgroundImage: 'none',
            boxShadow: isDark ? '0 18px 35px rgba(0, 0, 0, 0.45)' : '0 18px 35px rgba(44, 90, 131, 0.16)',
            bgcolor: isDark ? '#0f172a' : '#ffffff',
          }}
        >
          {step === 1 ? (
            <Box component="form" onSubmit={handleSendOtp} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography sx={{ color: isDark ? '#9fb5d1' : '#334155', fontSize: '1.05rem' }}>
                Step 1: Enter your account email to receive OTP.
              </Typography>

              <Box>
                <Typography variant="body1" sx={{ mb: 0.8, fontWeight: 700 }}>
                  Email Address
                </Typography>
                <TextField
                  fullWidth
                  placeholder="name@company.com"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      borderRadius: 1.2,
                    },
                  }}
                />
              </Box>

              {error && <Alert severity="error">{error}</Alert>}

              <Button
                type="submit"
                variant="contained"
                fullWidth
                sx={{
                  py: 1.05,
                  borderRadius: 1.2,
                  fontSize: '1.05rem',
                  fontWeight: 800,
                }}
                disabled={loading}
              >
                {loading ? 'Sending OTP...' : 'Send OTP'}
              </Button>
            </Box>
          ) : (
            <Box component="form" onSubmit={handleVerifyOtp} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography sx={{ color: isDark ? '#9fb5d1' : '#334155', fontSize: '1.05rem' }}>
                Step 2: Enter OTP sent to <strong>{email}</strong>.
              </Typography>

              {notice && <Alert severity="info">{notice}</Alert>}

              <Box>
                <Typography variant="body1" sx={{ mb: 0.8, fontWeight: 700 }}>
                  OTP Code
                </Typography>
                <TextField
                  fullWidth
                  placeholder="123456"
                  inputProps={{ maxLength: OTP_LENGTH, inputMode: 'numeric', pattern: '[0-9]*' }}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  helperText={otpHelperText}
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      borderRadius: 1.2,
                    },
                  }}
                />
              </Box>

              {error && <Alert severity="error">{error}</Alert>}

              <Button
                type="submit"
                variant="contained"
                fullWidth
                sx={{
                  py: 1.05,
                  borderRadius: 1.2,
                  fontSize: '1.05rem',
                  fontWeight: 800,
                }}
                disabled={loading}
              >
                {loading ? 'Verifying...' : 'Verify OTP'}
              </Button>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
                <Button variant="text" onClick={() => setStep(1)} sx={{ textTransform: 'none', px: 0, fontWeight: 700 }}>
                  Change email
                </Button>
                <Button
                  variant="text"
                  onClick={async () => {
                    setError('');
                    setNotice('');
                    setLoading(true);
                    try {
                      const result = await forgotPasswordSendOtpApi(email);
                      setResendSeconds(OTP_RESEND_SECONDS);
                      const expiresInMinutes = Math.max(Math.floor((result.expires_in ?? 0) / 60), 1);
                      setNotice(`OTP has been resent. It will expire in about ${expiresInMinutes} minutes.`);
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Failed to resend OTP.');
                    } finally {
                      setLoading(false);
                    }
                  }}
                  disabled={resendSeconds > 0}
                  sx={{ textTransform: 'none', px: 0, fontWeight: 700 }}
                >
                  {resendSeconds > 0 ? `Resend in ${resendSeconds}s` : 'Resend OTP'}
                </Button>
              </Box>
            </Box>
          )}
        </Paper>

        <Typography sx={{ mt: 2.3, color: isDark ? '#d4deed' : '#1f2937', textAlign: 'center', fontSize: '1.05rem' }}>
          Remember your password?{' '}
          <Link
            component={RouterLink}
            to="/login"
            sx={{ color: isDark ? '#7dd3fc' : '#256d95', textDecoration: 'none', fontWeight: 700, '&:hover': { textDecoration: 'underline' } }}
          >
            Sign In
          </Link>
        </Typography>
      </Box>
    </Box>
  );
};
