import React, { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Avatar,
  Box,
  Button,
  CircularProgress,
  Divider,
  Grid,
  Paper,
  Chip,
  Stack,
  TextField,
  Typography,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Link2, Link2Off, Save, Upload } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { useSnackbar } from '~components/AppLayout';
import { ensureAuthenticatedAccessToken, meApi } from '@/features/auth/api/authApi';
import { updateUserApi, uploadUserAvatarApi } from '@/features/users/api/userApi';
import {
  disconnectLinkedInApi,
  getLinkedInConnectionApi,
  startLinkedInConnectApi,
  type LinkedInConnectionStatus,
} from '../api/linkedinApi';
import {
  disconnectFacebookApi,
  getFacebookConnectionApi,
  startFacebookConnectApi,
  type FacebookConnectionStatus,
} from '../api/facebookApi';

type ProfileFormProps = {
  embedded?: boolean;
  hideHeader?: boolean;
  onSaved?: () => void;
};

type ProfileFormState = {
  user_name: string;
  email: string;
  full_name: string;
  phone: string;
  avatar_url: string;
};

const INITIAL_FORM: ProfileFormState = {
  user_name: '',
  email: '',
  full_name: '',
  phone: '',
  avatar_url: '',
};

const MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024;
const AVATAR_ACCEPTED_FORMATS = 'image/png,image/jpeg,image/webp,image/gif';

export const ProfileForm: React.FC<ProfileFormProps> = ({
  embedded = false,
  hideHeader = false,
  onSaved,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [form, setForm] = useState<ProfileFormState>(INITIAL_FORM);
  const [userId, setUserId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [connectingLinkedIn, setConnectingLinkedIn] = useState(false);
  const [disconnectingLinkedIn, setDisconnectingLinkedIn] = useState(false);
  const [linkedinConnection, setLinkedinConnection] = useState<LinkedInConnectionStatus | null>(null);
  const [connectingFacebook, setConnectingFacebook] = useState(false);
  const [disconnectingFacebook, setDisconnectingFacebook] = useState(false);
  const [facebookConnection, setFacebookConnection] = useState<FacebookConnectionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const avatarFileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let active = true;

    const loadProfile = async () => {
      const token = await ensureAuthenticatedAccessToken();
      if (!token) {
        navigate({ to: '/login' });
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const user = await meApi(token);
        if (!active) return;

        setUserId(user.id);
        setForm({
          user_name: user.user_name || '',
          email: user.email || '',
          full_name: user.full_name || '',
          phone: user.phone || '',
          avatar_url: user.avatar_url || '',
        });
        const linkedin = await getLinkedInConnectionApi(token);
        const facebook = await getFacebookConnectionApi(token);
        if (!active) return;
        setLinkedinConnection(linkedin);
        setFacebookConnection(facebook);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : t('profile.errors.loadFailed'));
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadProfile();
    return () => {
      active = false;
    };
  }, [navigate]);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get('linkedin') === 'connected') {
      showSnackbar(t('profile.linkedin.connected'), 'success');
      query.delete('linkedin');
      const nextQuery = query.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`;
      window.history.replaceState({}, '', nextUrl);
      void (async () => {
        const token = await ensureAuthenticatedAccessToken();
        if (!token) return;
        try {
          const linkedin = await getLinkedInConnectionApi(token);
          setLinkedinConnection(linkedin);
        } catch {
          // Ignore transient refresh/profile reload errors on callback landing.
        }
      })();
    }
    const linkedinError = query.get('linkedin_error');
    if (linkedinError) {
      showSnackbar(t('profile.linkedin.connectFailed'), 'error');
      query.delete('linkedin_error');
      const nextQuery = query.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`;
      window.history.replaceState({}, '', nextUrl);
    }

    if (query.get('facebook') === 'connected') {
      showSnackbar(t('profile.facebook.connected'), 'success');
      query.delete('facebook');
      const nextQuery = query.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`;
      window.history.replaceState({}, '', nextUrl);
      void (async () => {
        const token = await ensureAuthenticatedAccessToken();
        if (!token) return;
        try {
          const facebook = await getFacebookConnectionApi(token);
          setFacebookConnection(facebook);
        } catch {
          // Ignore transient refresh/profile reload errors on callback landing.
        }
      })();
    }
    const facebookError = query.get('facebook_error');
    if (facebookError) {
      showSnackbar(t('profile.facebook.connectFailed'), 'error');
      query.delete('facebook_error');
      const nextQuery = query.toString();
      const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`;
      window.history.replaceState({}, '', nextUrl);
    }
  }, [showSnackbar]);

  const setField = (key: keyof ProfileFormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const displayAvatarInitial = (form.full_name || form.user_name || form.email || '?')
    .trim()
    .charAt(0)
    .toUpperCase();

  const handleAvatarSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setError(t('profile.errors.invalidImage'));
      event.target.value = '';
      return;
    }

    if (file.size > MAX_AVATAR_SIZE_BYTES) {
      setError(t('profile.errors.avatarTooLarge'));
      event.target.value = '';
      return;
    }

    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      event.target.value = '';
      navigate({ to: '/login' });
      return;
    }

    if (!userId) {
      setError(t('profile.errors.invalidContext'));
      event.target.value = '';
      return;
    }

    try {
      setUploadingAvatar(true);
      setError(null);
      const updated = await uploadUserAvatarApi(token, userId, file);
      setForm((prev) => ({
        ...prev,
        avatar_url: updated.avatar_url || '',
      }));
      showSnackbar(t('profile.avatar.updated'), 'success');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.errors.avatarUploadFailed'));
    } finally {
      setUploadingAvatar(false);
      event.target.value = '';
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving) return;

    const userName = form.user_name.trim();
    const fullName = form.full_name.trim();
    const phone = form.phone.trim();
    const avatarUrl = form.avatar_url.trim();

    if (!userName) {
      setError(t('profile.errors.usernameRequired'));
      return;
    }

    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }

    if (!userId) {
      setError(t('profile.errors.invalidContext'));
      return;
    }

    try {
      setSaving(true);
      setError(null);
      const updated = await updateUserApi(token, userId, {
        user_name: userName,
        full_name: fullName || null,
        phone: phone || null,
        avatar_url: avatarUrl || null,
      });

      setForm((prev) => ({
        ...prev,
        user_name: updated.user_name || '',
        email: updated.email || '',
        full_name: updated.full_name || '',
        phone: updated.phone || '',
        avatar_url: updated.avatar_url || '',
      }));
      showSnackbar(t('profile.updated'), 'success');
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.errors.updateFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleConnectLinkedIn = async () => {
    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }
    try {
      setConnectingLinkedIn(true);
      setError(null);
      const returnTo = `${window.location.pathname}${window.location.search}`;
      const response = await startLinkedInConnectApi(token, returnTo);
      if (!response.authorize_url) {
        throw new Error(t('profile.linkedin.authUrlMissing'));
      }
      window.location.href = response.authorize_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.linkedin.startFailed'));
      setConnectingLinkedIn(false);
    }
  };

  const handleDisconnectLinkedIn = async () => {
    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }
    try {
      setDisconnectingLinkedIn(true);
      setError(null);
      await disconnectLinkedInApi(token);
      setLinkedinConnection((prev) =>
        prev
          ? { ...prev, connected: false, display_name: null, member_urn: null, expires_at: null }
          : {
              connected: false,
              provider: 'linkedin',
              display_name: null,
              member_urn: null,
              expires_at: null,
            },
      );
      showSnackbar(t('profile.linkedin.disconnected'), 'info');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.linkedin.disconnectFailed'));
    } finally {
      setDisconnectingLinkedIn(false);
    }
  };

  const handleConnectFacebook = async () => {
    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }
    try {
      setConnectingFacebook(true);
      setError(null);
      const returnTo = `${window.location.pathname}${window.location.search}`;
      const response = await startFacebookConnectApi(token, returnTo);
      if (!response.authorize_url) {
        throw new Error(t('profile.facebook.authUrlMissing'));
      }
      window.location.href = response.authorize_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.facebook.startFailed'));
      setConnectingFacebook(false);
    }
  };

  const handleDisconnectFacebook = async () => {
    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }
    try {
      setDisconnectingFacebook(true);
      setError(null);
      await disconnectFacebookApi(token);
      setFacebookConnection((prev) =>
        prev
          ? { ...prev, connected: false, display_name: null, account_id: null, expires_at: null }
          : {
              connected: false,
              provider: 'facebook',
              display_name: null,
              account_id: null,
              expires_at: null,
            },
      );
      showSnackbar(t('profile.facebook.disconnected'), 'info');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('profile.facebook.disconnectFailed'));
    } finally {
      setDisconnectingFacebook(false);
    }
  };

  const content = (
    <>
      {!hideHeader && (
        <>
          <Box sx={{ mb: 2 }}>
            <Typography variant="h5" sx={{ fontWeight: 800, mb: 0.5 }}>
              {t('profile.title')}
            </Typography>
            <Typography color="text.secondary">
              {t('profile.subtitle')}
            </Typography>
          </Box>
          <Divider sx={{ mb: 2.5 }} />
        </>
      )}

      {loading ? (
        <Box sx={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
          <CircularProgress size={18} />
          <Typography color="text.secondary">{t('profile.loading')}</Typography>
        </Box>
      ) : (
        <Box component="form" onSubmit={handleSubmit}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Stack
            spacing={1.5}
            alignItems="center"
            sx={{
              mb: 3,
              py: 1,
            }}
          >
            <Avatar
              src={form.avatar_url || undefined}
              alt={form.full_name || form.user_name || t('profile.avatar.alt')}
              sx={{
                width: 104,
                height: 104,
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: 'primary.light',
                color: 'primary.dark',
                fontSize: 34,
                fontWeight: 700,
              }}
            >
              {displayAvatarInitial}
            </Avatar>
            <Button
              type="button"
              variant="outlined"
              disabled={uploadingAvatar}
              startIcon={
                uploadingAvatar ? <CircularProgress size={14} color="inherit" /> : <Upload size={16} />
              }
              onClick={() => avatarFileInputRef.current?.click()}
              sx={{ minWidth: 220, fontWeight: 600 }}
            >
              {uploadingAvatar ? t('profile.avatar.uploading') : t('profile.avatar.choose')}
            </Button>
            <Typography variant="caption" color="text.secondary">
              {t('profile.avatar.hint')}
            </Typography>
            <input
              ref={avatarFileInputRef}
              hidden
              type="file"
              accept={AVATAR_ACCEPTED_FORMATS}
              onChange={handleAvatarSelect}
            />
          </Stack>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label={t('profile.fields.username')}
                value={form.user_name}
                onChange={(event) => setField('user_name', event.target.value)}
                required
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label={t('profile.fields.email')}
                type="email"
                value={form.email}
                disabled
                helperText={t('profile.fields.emailReadOnly')}
                sx={{
                  '& .MuiInputBase-input.Mui-disabled': { WebkitTextFillColor: '#6B7280' },
                }}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label={t('profile.fields.fullName')}
                value={form.full_name}
                onChange={(event) => setField('full_name', event.target.value)}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                label={t('profile.fields.phone')}
                value={form.phone}
                onChange={(event) => setField('phone', event.target.value)}
              />
            </Grid>
            <Grid item xs={12}>
              <Paper
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  p: { xs: 1.2, md: 1.5 },
                  borderColor: 'divider',
                }}
              >
                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  alignItems={{ xs: 'flex-start', md: 'center' }}
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontWeight: 700 }}>{t('profile.linkedin.title')}</Typography>
                    <Stack direction="row" spacing={0.8} alignItems="center" sx={{ mt: 0.55 }}>
                      <Chip
                        size="small"
                        color={linkedinConnection?.connected ? 'success' : 'default'}
                        label={linkedinConnection?.connected ? t('profile.connected') : t('profile.notConnected')}
                      />
                      {linkedinConnection?.display_name ? (
                        <Typography variant="body2" color="text.secondary">
                          {linkedinConnection.display_name}
                        </Typography>
                      ) : null}
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.55 }}>
                      {t('profile.linkedin.description')}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1}>
                    <Tooltip
                      title={
                        connectingLinkedIn
                          ? t('profile.connecting')
                          : linkedinConnection?.connected
                            ? t('profile.linkedin.reconnect')
                            : t('profile.linkedin.connect')
                      }
                      arrow
                    >
                      <span>
                        <IconButton
                          type="button"
                          disabled={connectingLinkedIn}
                          onClick={() => {
                            void handleConnectLinkedIn();
                          }}
                          aria-label={
                            linkedinConnection?.connected
                              ? t('profile.linkedin.reconnect')
                              : t('profile.linkedin.connect')
                          }
                          sx={{
                            width: 38,
                            height: 38,
                            borderRadius: 999,
                            color: '#ffffff',
                            background: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
                            '&:hover': {
                              background: 'linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%)',
                            },
                            '&.Mui-disabled': {
                              background: 'rgba(148,163,184,0.6)',
                              color: '#ffffff',
                            },
                          }}
                        >
                          {connectingLinkedIn ? (
                            <CircularProgress size={15} color="inherit" />
                          ) : (
                            <Link2 size={17} />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title={disconnectingLinkedIn ? t('profile.disconnecting') : t('profile.linkedin.disconnect')} arrow>
                      <span>
                        <IconButton
                          type="button"
                          disabled={disconnectingLinkedIn || !linkedinConnection?.connected}
                          onClick={() => {
                            void handleDisconnectLinkedIn();
                          }}
                          aria-label={t('profile.linkedin.disconnect')}
                          sx={{
                            width: 38,
                            height: 38,
                            borderRadius: 999,
                            border: '1px solid',
                            borderColor: 'divider',
                          }}
                        >
                          {disconnectingLinkedIn ? (
                            <CircularProgress size={15} color="inherit" />
                          ) : (
                            <Link2Off size={17} />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                  </Stack>
                </Stack>
              </Paper>
            </Grid>
            <Grid item xs={12}>
              <Paper
                variant="outlined"
                sx={{
                  borderRadius: 2,
                  p: { xs: 1.2, md: 1.5 },
                  borderColor: 'divider',
                }}
              >
                <Stack
                  direction={{ xs: 'column', md: 'row' }}
                  alignItems={{ xs: 'flex-start', md: 'center' }}
                  justifyContent="space-between"
                  spacing={1}
                >
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontWeight: 700 }}>{t('profile.facebook.title')}</Typography>
                    <Stack direction="row" spacing={0.8} alignItems="center" sx={{ mt: 0.55 }}>
                      <Chip
                        size="small"
                        color={facebookConnection?.connected ? 'success' : 'default'}
                        label={facebookConnection?.connected ? t('profile.connected') : t('profile.notConnected')}
                      />
                      {facebookConnection?.display_name ? (
                        <Typography variant="body2" color="text.secondary">
                          {facebookConnection.display_name}
                        </Typography>
                      ) : null}
                    </Stack>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.55 }}>
                      {t('profile.facebook.description')}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1}>
                    <Tooltip
                      title={
                        connectingFacebook
                          ? t('profile.connecting')
                          : facebookConnection?.connected
                            ? t('profile.facebook.reconnect')
                            : t('profile.facebook.connect')
                      }
                      arrow
                    >
                      <span>
                        <IconButton
                          type="button"
                          disabled={connectingFacebook}
                          onClick={() => {
                            void handleConnectFacebook();
                          }}
                          aria-label={
                            facebookConnection?.connected
                              ? t('profile.facebook.reconnect')
                              : t('profile.facebook.connect')
                          }
                          sx={{
                            width: 38,
                            height: 38,
                            borderRadius: 999,
                            color: '#ffffff',
                            background: 'linear-gradient(135deg, #1877f2 0%, #0b57d0 100%)',
                            '&:hover': {
                              background: 'linear-gradient(135deg, #166fe5 0%, #094db8 100%)',
                            },
                            '&.Mui-disabled': {
                              background: 'rgba(148,163,184,0.6)',
                              color: '#ffffff',
                            },
                          }}
                        >
                          {connectingFacebook ? (
                            <CircularProgress size={15} color="inherit" />
                          ) : (
                            <Link2 size={17} />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                    <Tooltip title={disconnectingFacebook ? t('profile.disconnecting') : t('profile.facebook.disconnect')} arrow>
                      <span>
                        <IconButton
                          type="button"
                          disabled={disconnectingFacebook || !facebookConnection?.connected}
                          onClick={() => {
                            void handleDisconnectFacebook();
                          }}
                          aria-label={t('profile.facebook.disconnect')}
                          sx={{
                            width: 38,
                            height: 38,
                            borderRadius: 999,
                            border: '1px solid',
                            borderColor: 'divider',
                          }}
                        >
                          {disconnectingFacebook ? (
                            <CircularProgress size={15} color="inherit" />
                          ) : (
                            <Link2Off size={17} />
                          )}
                        </IconButton>
                      </span>
                    </Tooltip>
                  </Stack>
                </Stack>
              </Paper>
            </Grid>
          </Grid>

          <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              type="submit"
              variant="contained"
              startIcon={saving ? <CircularProgress size={14} color="inherit" /> : <Save size={16} />}
              disabled={saving || uploadingAvatar}
              sx={{ minWidth: 150, fontWeight: 700 }}
            >
              {saving ? t('profile.saving') : t('common.save')}
            </Button>
          </Box>
        </Box>
      )}
    </>
  );

  if (embedded) {
    return (
      <Box sx={{ width: '100%', bgcolor: 'background.paper', p: { xs: 1.2, md: 1.8 } }}>
        {content}
      </Box>
    );
  }

  return (
    <Paper
      sx={{
        width: '100%',
        borderRadius: 3,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        p: { xs: 2.5, md: 3.5 },
      }}
    >
      {content}
    </Paper>
  );
};
