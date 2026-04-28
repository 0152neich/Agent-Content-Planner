import React from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  FormControl,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  TextField,
  Typography,
} from '@mui/material';
import ManageSearchRoundedIcon from '@mui/icons-material/ManageSearchRounded';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import { useNavigate } from '@tanstack/react-router';
import { MiniTaskbar } from '@/features/workspace/components/MiniTaskbar';
import { ProfileDialog } from '@/features/profile';
import { ProjectSettingsDialog } from '@/features/settings';
import { clearAccessToken } from '@/features/auth/authStorage';
import { logoutApi } from '@/features/auth/api/authApi';
import type { AutopostJobItem } from '@/features/workspace/types';
import { useAutoPostState } from '../hooks/useAutoPostState';

const toBadgeColor = (
  status: AutopostJobItem['status'],
): 'default' | 'success' | 'warning' | 'error' | 'info' => {
  if (status === 'PUBLISHED') return 'success';
  if (status === 'SCHEDULED') return 'info';
  if (status === 'NEEDS_RECONNECT') return 'warning';
  if (status === 'FAILED') return 'error';
  return 'default';
};

const formatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const toDateInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

const toTimeInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const AutoPostFeature: React.FC = () => {
  const navigate = useNavigate();
  const [profileDialogOpen, setProfileDialogOpen] = React.useState(false);
  const [projectSettingsOpen, setProjectSettingsOpen] = React.useState(false);
  const {
    user,
    project,
    jobs,
    loading,
    submitting,
    error,
    keyword,
    platform,
    publishMode,
    scheduledDate,
    scheduledTime,
    pageId,
    facebookPages,
    facebookPagesLoading,
    setKeyword,
    setPlatform,
    setPublishMode,
    setScheduledDate,
    setScheduledTime,
    setPageId,
    submitJob,
    retryJob,
    cancelJob,
    needsReconnect,
  } = useAutoPostState();

  const handleLogout = async () => {
    try {
      await logoutApi();
    } catch {
      // no-op
    } finally {
      clearAccessToken();
      navigate({ to: '/login' });
    }
  };

  const minScheduleDateTime = new Date(Date.now() + 30 * 60 * 1000);
  const minScheduleDate = toDateInput(minScheduleDateTime);
  const minScheduleTime = toTimeInput(minScheduleDateTime);
  const timeMinForSelectedDate = scheduledDate === minScheduleDate ? minScheduleTime : undefined;

  return (
    <Box
      sx={{
        width: '100vw',
        minHeight: '100dvh',
        height: '100dvh',
        display: 'grid',
        gridTemplateColumns: { xs: '1fr', md: '56px 1fr' },
        bgcolor: '#eef3f8',
      }}
    >
      <Box
        sx={{
          borderRight: { xs: 'none', md: '1px solid #d7e2ef' },
          borderBottom: { xs: '1px solid #d7e2ef', md: 'none' },
          height: { xs: '52px', md: '100%' },
        }}
      >
        <MiniTaskbar
          currentUser={user}
          onCreateProject={() => navigate({ to: '/welcome' })}
          onOpenProfile={() => setProfileDialogOpen(true)}
          onOpenSettings={() => setProjectSettingsOpen(true)}
          onRequestLogout={() => {
            void handleLogout();
          }}
          mobile={false}
          mode="autopost"
          onSwitchMode={(nextMode) => {
            if (nextMode === 'recreate') {
              navigate({ to: '/workspace' });
              return;
            }
            navigate({ to: '/autopost' });
          }}
        />
      </Box>

      <Box
        sx={{
          p: { xs: 2, md: 3 },
          overflowY: 'auto',
          background: 'radial-gradient(circle at 30% 0%, #f7fbff 0%, #eef3f8 58%, #e8edf4 100%)',
        }}
      >
        <Box sx={{ maxWidth: 920, mx: 'auto', py: { xs: 1, md: 2 } }}>
          <Typography variant="h3" sx={{ fontWeight: 800, mb: 0.75, fontSize: { xs: '2rem', md: '3rem' } }}>
            Auto-Post
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 3, fontWeight: 500 }}>
            Generate one post per execution, then publish now or schedule.
          </Typography>

          {project ? (
            <Alert
              severity="info"
              sx={{
                mb: 3,
                borderRadius: 2,
                border: '1px solid #b7d8ef',
                background: 'linear-gradient(180deg, #e8f6ff 0%, #dff2ff 100%)',
              }}
            >
              Active project: <strong>{project.name}</strong>
            </Alert>
          ) : null}

          {needsReconnect ? (
            <Alert
              severity="warning"
              action={
                <Button size="small" onClick={() => setProfileDialogOpen(true)}>
                  Reconnect
                </Button>
              }
              sx={{ mb: 2.5 }}
            >
              Some jobs require social reconnect.
            </Alert>
          ) : null}

          {error ? (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          ) : null}

          <Box
            sx={{
              mb: 4,
              py: 0.5,
            }}
          >
            <Stack spacing={2}>
              <Typography sx={{ fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.06em', color: '#5f6f84' }}>
                KEYWORD
              </Typography>
              <TextField
                placeholder="Enter keyword or topic..."
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                fullWidth
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <ManageSearchRoundedIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                }}
              />
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ mb: 0.7, fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.06em', color: '#5f6f84' }}>
                    PLATFORM
                  </Typography>
                  <FormControl fullWidth>
                    <InputLabel id="autopost-platform-label" shrink={false}>
                      {platform ? '' : 'Platform'}
                    </InputLabel>
                    <Select
                      labelId="autopost-platform-label"
                      value={platform}
                      displayEmpty
                      onChange={(event) => setPlatform(event.target.value as 'linkedin' | 'facebook')}
                    >
                      <MenuItem value="linkedin">LinkedIn</MenuItem>
                      <MenuItem value="facebook">Facebook</MenuItem>
                    </Select>
                  </FormControl>
                </Box>
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
                  <Typography sx={{ mb: 0.7, fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.06em', color: '#5f6f84' }}>
                    PUBLISH MODE
                  </Typography>
                  <ToggleButtonGroup
                    exclusive
                    value={publishMode}
                    onChange={(_event, value: 'now' | 'schedule' | null) => {
                      if (value) setPublishMode(value);
                    }}
                    sx={{
                      width: '100%',
                      maxWidth: 420,
                      alignSelf: 'stretch',
                      '& .MuiToggleButtonGroup-grouped': {
                        flex: 1,
                        textTransform: 'none',
                        fontWeight: 700,
                        borderRadius: 1.8,
                        borderColor: '#b9cbe0',
                        color: '#3a4d64',
                        minHeight: 42,
                        bgcolor: '#dbe7f4',
                      },
                      '& .MuiToggleButtonGroup-grouped:not(:first-of-type)': {
                        marginLeft: '8px',
                        borderLeft: '1px solid #b9cbe0',
                      },
                      '& .MuiToggleButtonGroup-grouped.Mui-selected': {
                        bgcolor: '#ffffff',
                        color: '#0f2a49',
                        borderColor: '#8fb2d8',
                        boxShadow: '0 0 0 1px rgba(143,178,216,0.35) inset',
                      },
                    }}
                  >
                    <ToggleButton value="now">Publish now</ToggleButton>
                    <ToggleButton value="schedule">Schedule</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
              </Stack>
              {publishMode === 'schedule' ? (
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ mb: 0.7, fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.06em', color: '#5f6f84' }}>
                      DATE
                    </Typography>
                    <TextField
                      type="date"
                      fullWidth
                      value={scheduledDate}
                      onChange={(event) => setScheduledDate(event.target.value)}
                      inputProps={{ min: minScheduleDate }}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ mb: 0.7, fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.06em', color: '#5f6f84' }}>
                      TIME
                    </Typography>
                    <TextField
                      type="time"
                      fullWidth
                      value={scheduledTime}
                      onChange={(event) => setScheduledTime(event.target.value)}
                      inputProps={timeMinForSelectedDate ? { min: timeMinForSelectedDate } : undefined}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Box>
                </Stack>
              ) : null}
              <Box
                sx={{
                  px: 1.25,
                  py: 1,
                  borderRadius: 1.5,
                  border: '1px solid #c8d8ea',
                  bgcolor: '#edf3fb',
                  color: '#2a4464',
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.8,
                }}
              >
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#3b82f6', flexShrink: 0 }} />
                {publishMode === 'now'
                  ? 'Summary: This post will be published immediately after generation.'
                  : `Scheduled -> ${new Date(`${scheduledDate}T${scheduledTime}`).toLocaleString()}`}
              </Box>
              {platform === 'facebook' ? (
                <FormControl fullWidth>
                  <InputLabel id="autopost-page-label">Facebook page</InputLabel>
                  <Select
                    labelId="autopost-page-label"
                    label="Facebook page"
                    value={pageId}
                    onChange={(event) => setPageId(String(event.target.value))}
                    disabled={facebookPagesLoading}
                  >
                    {facebookPages.map((page) => (
                      <MenuItem key={page.id} value={page.id}>
                        {page.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              ) : null}
              <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="contained"
                  onClick={() => void submitJob()}
                  disabled={submitting}
                  sx={{ minWidth: 130, borderRadius: 2.5, fontWeight: 700 }}
                >
                  {submitting ? 'Submitting...' : 'Execute'}
                </Button>
              </Box>
            </Stack>
          </Box>

          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
            Timeline
          </Typography>
          {loading ? (
            <CircularProgress size={20} />
          ) : jobs.length === 0 ? (
            <Box
              sx={{
                borderTop: '1px dashed',
                borderBottom: '1px dashed',
                borderColor: '#c9d6e3',
                px: 3,
                py: 8,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1.5,
                color: 'text.secondary',
              }}
            >
              <ScheduleOutlinedIcon sx={{ fontSize: 56, color: '#7f8ea3' }} />
              <Typography color="text.secondary">No auto-post jobs yet.</Typography>
            </Box>
          ) : (
            <Stack spacing={1.5}>
              {jobs.map((job) => (
                <Box
                  key={job.id}
                  sx={{
                    p: 1.5,
                    borderBottom: '1px solid',
                    borderColor: '#d8e2ee',
                  }}
                >
                  <Stack
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={1}
                    alignItems={{ xs: 'flex-start', md: 'center' }}
                    justifyContent="space-between"
                  >
                    <Box>
                      <Typography sx={{ fontWeight: 700 }}>{job.keyword}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        {job.platform.toUpperCase()} - {formatDate(job.scheduled_at)}
                      </Typography>
                      {job.error_message ? (
                        <Typography variant="body2" color="error.main" sx={{ mt: 0.5 }}>
                          {job.error_message}
                        </Typography>
                      ) : null}
                    </Box>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip size="small" label={job.status} color={toBadgeColor(job.status)} />
                      {(job.status === 'FAILED' || job.status === 'NEEDS_RECONNECT') ? (
                        <Button size="small" onClick={() => void retryJob(job.id)}>
                          Retry
                        </Button>
                      ) : null}
                      {job.status !== 'PUBLISHED' && job.status !== 'CANCELLED' ? (
                        <Button size="small" color="error" onClick={() => void cancelJob(job.id)}>
                          Cancel
                        </Button>
                      ) : null}
                    </Stack>
                  </Stack>
                </Box>
              ))}
            </Stack>
          )}
        </Box>
      </Box>

      <ProfileDialog open={profileDialogOpen} onClose={() => setProfileDialogOpen(false)} />
      <ProjectSettingsDialog open={projectSettingsOpen} onClose={() => setProjectSettingsOpen(false)} />
    </Box>
  );
};

export default AutoPostFeature;
