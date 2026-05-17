import React from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputAdornment,
  InputLabel,
  Menu,
  MenuItem,
  Paper,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  TextField,
  Typography,
} from '@mui/material';
import ArrowForwardIosRoundedIcon from '@mui/icons-material/ArrowForwardIosRounded';
import FacebookIcon from '@mui/icons-material/Facebook';
import LinkedInIcon from '@mui/icons-material/LinkedIn';
import ManageSearchRoundedIcon from '@mui/icons-material/ManageSearchRounded';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import { useNavigate } from '@tanstack/react-router';
import { MiniTaskbar } from '@/features/workspace/components/MiniTaskbar';
import { ProfileDialog } from '@/features/profile';
import { ProjectSettingsDialog } from '@/features/settings';
import { clearAccessToken } from '@/features/auth/authStorage';
import { logoutApi } from '@/features/auth/api/authApi';
import { SocialCardFacebook } from '@/features/workspace/components/SocialCardFacebook';
import { SocialCardLinkedIn } from '@/features/workspace/components/SocialCardLinkedIn';
import type { AutopostJobItem } from '@/features/workspace/types';
import { setWorkspaceIntent } from '@/features/workspace/workspaceIntentStorage';
import { useAutoPostState } from '../hooks/useAutoPostState';
import type {
  AutoPostConnectPrompt,
  AutoPostFeedFilter,
  CurrentChatDraftItem,
} from '../hooks/useAutoPostState';

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

const toDraftExcerpt = (value: string, max = 180): string => {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= max) return normalized;
  return `${normalized.slice(0, max).trim()}...`;
};

const toJobTitle = (job: AutopostJobItem): string => {
  const content = (job.final_content || job.draft_content || '').replace(/\s+/g, ' ').trim();
  if (content) {
    return toDraftExcerpt(content, 110);
  }
  const keyword = (job.keyword || '').replace(/\s+/g, ' ').trim();
  const cleaned = keyword.replace(
    /^manual content \((linkedin|facebook)\)\s*(\[[a-f0-9]{8,}\])?\s*/i,
    '',
  ).trim();
  return cleaned || keyword || 'Auto-post draft';
};

const formatScheduleSummary = (dateText: string, timeText: string): string => {
  const parsed = new Date(`${dateText}T${timeText}`);
  if (Number.isNaN(parsed.getTime())) return 'Scheduled -> Invalid date';
  return `Scheduled -> ${parsed.toLocaleString()}`;
};

const includesDraftFilter = (draft: CurrentChatDraftItem, filter: AutoPostFeedFilter): boolean => {
  if (filter === 'all') return true;
  if (filter === 'scheduled') return false;
  if (filter === 'unscheduled') return true;
  return draft.platform.toLowerCase() === filter;
};

const includesJobFilter = (status: AutopostJobItem['status'], platform: string, filter: AutoPostFeedFilter): boolean => {
  if (filter === 'all') return true;
  if (filter === 'scheduled') return status === 'SCHEDULED';
  if (filter === 'unscheduled') return status !== 'SCHEDULED';
  return platform.toLowerCase() === filter;
};

const FEED_FILTER_OPTIONS: Array<{ value: AutoPostFeedFilter; label: string }> = [
  { value: 'all', label: 'Tất cả' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'scheduled', label: 'Đã lên lịch' },
  { value: 'unscheduled', label: 'Chưa lên lịch' },
];

const resolveConnectPromptText = (prompt: AutoPostConnectPrompt): string => {
  if (prompt.message.trim()) {
    return prompt.message;
  }
  if (prompt.platform === 'facebook') {
    return 'Facebook account is not connected. Please connect to continue.';
  }
  if (prompt.platform === 'linkedin') {
    return 'LinkedIn account is not connected. Please connect to continue.';
  }
  return 'Your social account is not connected. Please connect to continue.';
};

const AutoPostFeature: React.FC = () => {
  const navigate = useNavigate();
  const [profileDialogOpen, setProfileDialogOpen] = React.useState(false);
  const [projectSettingsOpen, setProjectSettingsOpen] = React.useState(false);
  const [previewOpen, setPreviewOpen] = React.useState(false);
  const [scheduleDialogOpen, setScheduleDialogOpen] = React.useState(false);
  const [selectedDraft, setSelectedDraft] = React.useState<CurrentChatDraftItem | null>(null);
  const [dialogPublishMode, setDialogPublishMode] = React.useState<'now' | 'schedule'>('now');
  const [dialogScheduledDate, setDialogScheduledDate] = React.useState('');
  const [dialogScheduledTime, setDialogScheduledTime] = React.useState('');
  const [dialogPageId, setDialogPageId] = React.useState('');
  const [draftMenuAnchorEl, setDraftMenuAnchorEl] = React.useState<HTMLElement | null>(null);
  const [draftMenuTarget, setDraftMenuTarget] = React.useState<CurrentChatDraftItem | null>(null);
  const [dismissedDraftKeys, setDismissedDraftKeys] = React.useState<string[]>([]);

  const {
    user,
    projects,
    activeProjectId,
    jobs,
    currentChatDrafts,
    feedFilter,
    loading,
    submitting,
    error,
    connectPrompt,
    keyword,
    platform,
    publishMode,
    scheduledDate,
    scheduledTime,
    pageId,
    scheduleProjectId,
    dialogProjectId,
    facebookPages,
    facebookPagesLoading,
    setFeedFilter,
    setKeyword,
    setPlatform,
    setPublishMode,
    setScheduledDate,
    setScheduledTime,
    setPageId,
    setScheduleProjectId,
    setDialogProjectId,
    dismissConnectPrompt,
    startSocialConnect,
    submitJob,
    retryJob,
    cancelJob,
    scheduleFromContent,
    switchProject,
  } = useAutoPostState();

  const minScheduleDateTime = new Date(Date.now() + 30 * 60 * 1000);
  const minScheduleDate = toDateInput(minScheduleDateTime);
  const minScheduleTime = toTimeInput(minScheduleDateTime);
  const timeMinForSelectedDate = scheduledDate === minScheduleDate ? minScheduleTime : undefined;
  const dialogTimeMinForSelectedDate =
    dialogScheduledDate === minScheduleDate ? minScheduleTime : undefined;
  const scheduleSummaryText = formatScheduleSummary(scheduledDate, scheduledTime);
  const dialogScheduleSummaryText = formatScheduleSummary(dialogScheduledDate, dialogScheduledTime);
  const topFormFieldSx = {
    '& .MuiOutlinedInput-root': {
      height: 48,
      borderRadius: 1.35,
      bgcolor: '#ffffff',
      '& fieldset': { borderColor: '#c5ccd6' },
      '&:hover fieldset': { borderColor: '#9ea9b7' },
      '&.Mui-focused fieldset': { borderColor: '#2a70c8', boxShadow: '0 0 0 3px rgba(42,112,200,0.15)' },
    },
    '& .MuiInputBase-input': {
      fontSize: '0.98rem',
      color: '#202939',
    },
  } as const;

  const filteredDrafts = React.useMemo(
    () =>
      currentChatDrafts.filter((item) => {
        const key = `${item.projectId}-${item.platform}-${item.runId}`;
        return includesDraftFilter(item, feedFilter) && !dismissedDraftKeys.includes(key);
      }),
    [currentChatDrafts, dismissedDraftKeys, feedFilter],
  );

  const filteredJobs = React.useMemo(
    () => jobs.filter((item) => includesJobFilter(item.status, item.platform, feedFilter)),
    [feedFilter, jobs],
  );

  const openDraftPreview = (draft: CurrentChatDraftItem) => {
    setSelectedDraft(draft);
    setPreviewOpen(true);
  };

  const openDraftMenu = (event: React.MouseEvent<HTMLElement>, draft: CurrentChatDraftItem) => {
    event.stopPropagation();
    setDraftMenuAnchorEl(event.currentTarget);
    setDraftMenuTarget(draft);
  };

  const closeDraftMenu = () => {
    setDraftMenuAnchorEl(null);
    setDraftMenuTarget(null);
  };

  const openScheduleDialog = (draft: CurrentChatDraftItem) => {
    const nowPlus30 = new Date(Date.now() + 30 * 60 * 1000);
    setSelectedDraft(draft);
    setDialogPublishMode('now');
    setDialogScheduledDate(toDateInput(nowPlus30));
    setDialogScheduledTime(toTimeInput(nowPlus30));
    setDialogProjectId(draft.projectId);
    if (draft.platform === 'facebook') {
      setPlatform('facebook');
      setDialogPageId(pageId || '');
    } else {
      setDialogPageId('');
    }
    setPreviewOpen(false);
    setScheduleDialogOpen(true);
  };

  const handleEditContent = () => {
    if (!selectedDraft) return;
    switchProject(selectedDraft.projectId);
    setWorkspaceIntent({
      source: 'autopost',
      target_platform: selectedDraft.platform,
      timestamp: new Date().toISOString(),
    });
    setPreviewOpen(false);
    navigate({ to: '/workspace' });
  };

  const handleScheduleFromDraft = async () => {
    if (!selectedDraft) return;
    const ok = await scheduleFromContent({
      projectId: dialogProjectId,
      platform: selectedDraft.platform,
      content: selectedDraft.content,
      publishMode: dialogPublishMode,
      scheduledDate: dialogScheduledDate,
      scheduledTime: dialogScheduledTime,
      pageId: selectedDraft.platform === 'facebook' ? dialogPageId : undefined,
    });
    if (ok) {
      setScheduleDialogOpen(false);
    }
  };

  const handleMenuEditContent = () => {
    if (!draftMenuTarget) return;
    setSelectedDraft(draftMenuTarget);
    closeDraftMenu();
    switchProject(draftMenuTarget.projectId);
    setWorkspaceIntent({
      source: 'autopost',
      target_platform: draftMenuTarget.platform,
      timestamp: new Date().toISOString(),
    });
    navigate({ to: '/workspace' });
  };

  const handleMenuSchedule = () => {
    if (!draftMenuTarget) return;
    setSelectedDraft(draftMenuTarget);
    closeDraftMenu();
    openScheduleDialog(draftMenuTarget);
  };

  const handleMenuDelete = () => {
    if (!draftMenuTarget) return;
    const key = `${draftMenuTarget.projectId}-${draftMenuTarget.platform}-${draftMenuTarget.runId}`;
    setDismissedDraftKeys((prev) => (prev.includes(key) ? prev : [...prev, key]));
    if (selectedDraft?.runId === draftMenuTarget.runId
      && selectedDraft.platform === draftMenuTarget.platform
      && selectedDraft.projectId === draftMenuTarget.projectId) {
      setPreviewOpen(false);
      setScheduleDialogOpen(false);
      setSelectedDraft(null);
    }
    closeDraftMenu();
  };

  const handleOpenScheduleFromPreview = () => {
    if (!selectedDraft) return;
    openScheduleDialog(selectedDraft);
  };

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

  const handleSelectProjectFromTaskbar = (projectId: string) => {
    switchProject(projectId);
    navigate({ to: '/workspace' });
  };

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
          projects={projects}
          activeProjectId={activeProjectId}
          onSelectProject={handleSelectProjectFromTaskbar}
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
        <Box sx={{ maxWidth: 990, mx: 'auto', py: { xs: 1, md: 2 } }}>
          <Typography
            variant="h2"
            sx={{
              fontWeight: 800,
              mb: 0.8,
              fontSize: { xs: '2.8rem', md: '4rem' },
              letterSpacing: '-0.02em',
              color: '#2b3548',
              lineHeight: 1.08,
            }}
          >
            Auto-Post
          </Typography>
          <Typography
            variant="h5"
            sx={{
              mb: 3.2,
              fontWeight: 500,
              color: '#5a6472',
              fontSize: { xs: '1.4rem', md: '1.9rem' },
              lineHeight: 1.3,
            }}
          >
            Generate one post per execution, then publish now or schedule.
          </Typography>
          {error ? (
            <Alert severity="error" sx={{ mb: 2.5 }}>
              {error}
            </Alert>
          ) : null}
          {connectPrompt ? (
            <Alert
              severity="warning"
              sx={{ mb: 2.5 }}
              action={(
                <Stack direction="row" spacing={1}>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => {
                      void startSocialConnect(() => setProfileDialogOpen(true));
                    }}
                  >
                    Connect
                  </Button>
                  <Button size="small" onClick={dismissConnectPrompt}>
                    Dismiss
                  </Button>
                </Stack>
              )}
            >
              {resolveConnectPromptText(connectPrompt)}
            </Alert>
          ) : null}

          <Paper
            sx={{
              mb: 4,
              p: { xs: 2, md: 3 },
              borderRadius: 2.6,
              border: '1px solid #d5dce5',
              background: '#ffffff',
              boxShadow: '0 12px 28px rgba(22, 41, 69, 0.08)',
            }}
          >
            <Stack spacing={2.2}>
              <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.04em', color: '#5b6574' }}>
                KEYWORD
              </Typography>
              <TextField
                placeholder="Enter keyword or topic..."
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                fullWidth
                sx={topFormFieldSx}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <ManageSearchRoundedIcon sx={{ color: '#9da6b4' }} />
                    </InputAdornment>
                  ),
                }}
              />
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ mb: 0.7, fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.04em', color: '#5b6574' }}>
                    PROJECT
                  </Typography>
                  <FormControl fullWidth sx={topFormFieldSx}>
                    <InputLabel id="autopost-project-label">Project</InputLabel>
                    <Select
                      labelId="autopost-project-label"
                      label="Project"
                      value={scheduleProjectId}
                      onChange={(event) => setScheduleProjectId(String(event.target.value))}
                    >
                      {projects.map((item) => (
                        <MenuItem key={item.id} value={item.id}>
                          {item.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ mb: 0.7, fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.04em', color: '#5b6574' }}>
                    PLATFORM
                  </Typography>
                  <FormControl fullWidth sx={topFormFieldSx}>
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
                  <Typography sx={{ mb: 0.7, fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.04em', color: '#5b6574' }}>
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
                      maxWidth: 430,
                      alignSelf: 'stretch',
                      borderRadius: 1.35,
                      '& .MuiToggleButtonGroup-grouped': {
                        flex: 1,
                        textTransform: 'none',
                        fontWeight: 500,
                        fontSize: '0.95rem',
                        borderRadius: 1.2,
                        borderColor: '#c5ccd6',
                        color: '#334155',
                        minHeight: 48,
                        bgcolor: '#f8fafc',
                      },
                      '& .MuiToggleButtonGroup-grouped:not(:first-of-type)': {
                        marginLeft: '6px',
                        borderLeft: '1px solid #c5ccd6',
                      },
                      '& .MuiToggleButtonGroup-grouped.Mui-selected': {
                        bgcolor: '#104f86',
                        color: '#ffffff',
                        borderColor: '#104f86',
                        boxShadow: '0 6px 14px rgba(16, 79, 134, 0.25)',
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
                    <Typography sx={{ mb: 0.7, fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.04em', color: '#5b6574' }}>
                      DATE
                    </Typography>
                    <TextField
                      type="date"
                      fullWidth
                      value={scheduledDate}
                      onChange={(event) => setScheduledDate(event.target.value)}
                      inputProps={{ min: minScheduleDate }}
                      sx={topFormFieldSx}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Box>
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ mb: 0.7, fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.04em', color: '#5b6574' }}>
                      TIME
                    </Typography>
                    <TextField
                      type="time"
                      fullWidth
                      value={scheduledTime}
                      onChange={(event) => setScheduledTime(event.target.value)}
                      inputProps={timeMinForSelectedDate ? { min: timeMinForSelectedDate } : undefined}
                      sx={topFormFieldSx}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Box>
                </Stack>
              ) : null}
              <Box
                sx={{
                  px: 1.5,
                  py: 1.2,
                  borderRadius: 1.45,
                  border: '1px solid #e1e6ee',
                  bgcolor: '#f5f7fa',
                  color: '#2e3746',
                  fontSize: '0.95rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.8,
                }}
              >
                <Box sx={{ width: 11, height: 11, borderRadius: '50%', bgcolor: '#66a6e4', flexShrink: 0 }} />
                <Typography component="span" sx={{ fontWeight: 700 }}>
                  Summary:
                </Typography>
                <Typography component="span" sx={{ fontSize: '0.95rem' }}>
                  {publishMode === 'now'
                    ? 'This post will be published immediately after generation.'
                    : scheduleSummaryText}
                </Typography>
              </Box>
              {platform === 'facebook' ? (
                <FormControl fullWidth sx={topFormFieldSx}>
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
              <Box sx={{ borderTop: '1px solid #e2e7ee', pt: 2.1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  variant="contained"
                  onClick={() => void submitJob()}
                  disabled={submitting}
                  sx={{
                    minWidth: 132,
                    borderRadius: 1.35,
                    px: 2.6,
                    py: 0.9,
                    fontWeight: 700,
                    textTransform: 'none',
                    fontSize: '1.05rem',
                    background: 'linear-gradient(180deg, #0e66c9 0%, #0a4ea2 100%)',
                    boxShadow: '0 10px 18px rgba(10, 78, 162, 0.34)',
                    '&:hover': {
                      background: 'linear-gradient(180deg, #0d5eb8 0%, #0a4694 100%)',
                    },
                  }}
                >
                  {submitting ? 'Submitting...' : 'Execute'}
                </Button>
              </Box>
            </Stack>
          </Paper>

          <Box sx={{ mb: 5 }}>
            <Stack spacing={1.8}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#111827' }}>
                Feed Filter
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {FEED_FILTER_OPTIONS.map(({ value, label }) => (
                  <Chip
                    key={value}
                    label={label}
                    clickable
                    onClick={() => setFeedFilter(value)}
                    variant="outlined"
                    sx={{
                      borderRadius: 999,
                      height: 42,
                      px: 0.55,
                      fontWeight: 500,
                      bgcolor: feedFilter === value ? '#1e88e5' : 'rgba(255,255,255,0.3)',
                      color: feedFilter === value ? '#ffffff' : '#4b5563',
                      borderColor: feedFilter === value ? '#1e88e5' : '#aeb8c5',
                      boxShadow: feedFilter === value ? '0 8px 18px rgba(30, 136, 229, 0.28)' : 'none',
                      '&:hover': {
                        bgcolor: feedFilter === value ? '#1777ca' : 'rgba(255,255,255,0.56)',
                      },
                      '& .MuiChip-label': { px: 1.5, lineHeight: 1, fontSize: '0.96rem' },
                    }}
                  />
                ))}
              </Stack>
            </Stack>
          </Box>

          <Box sx={{ mb: 3.5 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#111827' }}>
                Current Chat Drafts
              </Typography>
              <Chip
                size="small"
                label={`${filteredDrafts.length} draft${filteredDrafts.length === 1 ? '' : 's'}`}
                sx={{
                  height: 36,
                  borderRadius: 999,
                  bgcolor: '#dce3eb',
                  color: '#111827',
                  fontWeight: 700,
                  '& .MuiChip-label': { px: 1.3, fontSize: '0.95rem' },
                }}
              />
            </Stack>
            {loading ? (
              <CircularProgress size={20} sx={{ mb: 1 }} />
            ) : filteredDrafts.length === 0 ? (
              <Box
                sx={{
                  border: '1px dashed #c9d6e3',
                  borderRadius: 3,
                  px: 2.5,
                  py: 4,
                  color: 'text.secondary',
                  bgcolor: 'rgba(255,255,255,0.7)',
                }}
              >
                <Typography color="text.secondary">No current chat drafts for this filter.</Typography>
              </Box>
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: {
                    xs: 'repeat(1, minmax(0, 1fr))',
                    sm: 'repeat(2, minmax(0, 1fr))',
                    md: 'repeat(3, minmax(0, 1fr))',
                    lg: 'repeat(4, minmax(0, 1fr))',
                  },
                  gap: 2,
                }}
              >
                {filteredDrafts.map((draft) => (
                  <Paper
                    key={`${draft.projectId}-${draft.platform}-${draft.runId}`}
                    onClick={() => openDraftPreview(draft)}
                    onContextMenu={(event) => {
                      event.preventDefault();
                      openDraftMenu(event, draft);
                    }}
                    sx={{
                      minHeight: 270,
                      borderRadius: 2.5,
                      border: '1px solid #d6dce5',
                      background: '#ffffff',
                      cursor: 'pointer',
                      position: 'relative',
                      overflow: 'hidden',
                      display: 'flex',
                      flexDirection: 'column',
                      transition: 'transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease',
                      boxShadow: '0 8px 24px rgba(15, 23, 42, 0.08)',
                      '&:hover': {
                        transform: 'translateY(-1px)',
                        boxShadow: '0 14px 30px rgba(15, 23, 42, 0.14)',
                        borderColor: '#b8c2ce',
                      },
                    }}
                  >
                    <Box sx={{ p: 2.2, pb: 0 }}>
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 0 }}>
                        <Box
                          sx={{
                            width: 40,
                            height: 40,
                            borderRadius: 1.2,
                            bgcolor: '#edf4fc',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: draft.platform === 'facebook' ? '#1877f2' : '#0a66c2',
                            flexShrink: 0,
                          }}
                        >
                          {draft.platform === 'facebook' ? (
                            <FacebookIcon sx={{ fontSize: 27 }} />
                          ) : (
                            <LinkedInIcon sx={{ fontSize: 27 }} />
                          )}
                        </Box>
                        <Chip
                          size="small"
                          label={draft.projectName}
                          variant="filled"
                          sx={{
                            height: 30,
                            minWidth: 0,
                            maxWidth: '100%',
                            bgcolor: '#e7ebf1',
                            color: '#111827',
                            fontWeight: 500,
                            '& .MuiChip-label': {
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              px: 1.3,
                              fontSize: '0.95rem',
                            },
                          }}
                        />
                      </Stack>
                    </Box>
                    <Box sx={{ p: 2.2, pt: 1.6, flex: 1, display: 'flex', flexDirection: 'column' }}>
                      <Typography sx={{ fontSize: '0.82rem', color: '#6b7280', mb: 1.4 }}>
                        Updated {formatDate(draft.updatedAt)}
                      </Typography>
                      <Typography
                        sx={{
                          color: '#111827',
                          wordBreak: 'break-word',
                          display: '-webkit-box',
                          overflow: 'hidden',
                          WebkitLineClamp: 4,
                          WebkitBoxOrient: 'vertical',
                          lineHeight: 1.42,
                          fontSize: '1.08rem',
                          flex: 1,
                        }}
                      >
                        {toDraftExcerpt(draft.content)}
                      </Typography>
                    </Box>
                    <Box
                      sx={{
                        px: 2.2,
                        py: 1.35,
                        borderTop: '1px solid #e7ebf0',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.8,
                        color: '#111827',
                      }}
                    >
                      <Typography
                        sx={{
                          fontSize: '1rem',
                          fontWeight: 500,
                          lineHeight: 1.2,
                        }}
                      >
                        Click to preview and schedule
                      </Typography>
                      <ArrowForwardIosRoundedIcon sx={{ fontSize: 15, color: '#374151' }} />
                    </Box>
                  </Paper>
                ))}
              </Box>
            )}
          </Box>

          <Paper
            sx={{
              borderRadius: 3,
              border: '1px solid #d5dce5',
              p: { xs: 2, md: 2.4 },
              background: 'rgba(255,255,255,0.88)',
              boxShadow: '0 12px 30px rgba(15, 23, 42, 0.06)',
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 700, color: '#111827', mb: 2.1 }}>
              AutoPost Jobs Timeline
            </Typography>
            {loading ? (
              <CircularProgress size={20} />
            ) : filteredJobs.length === 0 ? (
              <Box
                sx={{
                  border: '1px dashed #c8cfd9',
                  borderRadius: 2.2,
                  px: 3.5,
                  py: { xs: 6, md: 8 },
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2.2,
                  color: 'text.secondary',
                  bgcolor: 'rgba(255,255,255,0.55)',
                }}
              >
                <ScheduleOutlinedIcon sx={{ fontSize: 60, color: '#7a8595' }} />
                <Typography sx={{ color: '#4b5563' }}>No auto-post jobs yet.</Typography>
              </Box>
            ) : (
              <Stack spacing={1.25}>
                {filteredJobs.map((job) => (
                  <Paper
                    key={job.id}
                    variant="outlined"
                    sx={{
                      p: 1.4,
                      borderColor: '#d8e2ee',
                      borderRadius: 1.8,
                      bgcolor: '#fbfdff',
                    }}
                  >
                    <Stack
                      direction={{ xs: 'column', md: 'row' }}
                      spacing={1}
                      alignItems={{ xs: 'flex-start', md: 'center' }}
                      justifyContent="space-between"
                    >
                      <Box>
                        <Typography sx={{ fontWeight: 700 }}>{toJobTitle(job)}</Typography>
                        <Typography variant="body2" color="text.secondary">
                          {job.project_name} • {job.platform.toUpperCase()} • {formatDate(job.scheduled_at)}
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
                  </Paper>
                ))}
              </Stack>
            )}
          </Paper>
        </Box>
      </Box>

      <Menu
        anchorEl={draftMenuAnchorEl}
        open={Boolean(draftMenuAnchorEl && draftMenuTarget)}
        onClose={closeDraftMenu}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <MenuItem onClick={handleMenuDelete} sx={{ color: 'error.main' }}>
          Xóa bài nháp
        </MenuItem>
        <MenuItem onClick={handleMenuEditContent}>Chỉnh sửa nội dung</MenuItem>
        <MenuItem onClick={handleMenuSchedule}>Chỉnh sửa thông tin để lên lịch</MenuItem>
      </Menu>

      <Dialog open={previewOpen && Boolean(selectedDraft)} onClose={() => setPreviewOpen(false)} maxWidth="md" fullWidth>
        <DialogContent dividers>
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
            {selectedDraft?.platform === 'facebook' ? (
              <SocialCardFacebook content={selectedDraft.content} />
            ) : (
              <SocialCardLinkedIn content={selectedDraft?.content || ''} />
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button onClick={() => setPreviewOpen(false)}>Close</Button>
          <Button variant="outlined" onClick={handleEditContent}>
            Chỉnh sửa nội dung
          </Button>
          <Button variant="contained" onClick={handleOpenScheduleFromPreview}>
            Chỉnh sửa thông tin để lên lịch
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={scheduleDialogOpen && Boolean(selectedDraft)}
        onClose={() => setScheduleDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>
          Schedule Draft {selectedDraft ? `- ${selectedDraft.platform.toUpperCase()}` : ''}
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 0.5 }}>
            {error ? (
              <Alert severity="error">
                {error}
              </Alert>
            ) : null}
            {connectPrompt ? (
              <Alert
                severity="warning"
                action={(
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant="contained"
                      onClick={() => {
                        void startSocialConnect(() => setProfileDialogOpen(true));
                      }}
                    >
                      Connect
                    </Button>
                    <Button size="small" onClick={dismissConnectPrompt}>
                      Dismiss
                    </Button>
                  </Stack>
                )}
              >
                {resolveConnectPromptText(connectPrompt)}
              </Alert>
            ) : null}
            <FormControl fullWidth>
              <InputLabel id="dialog-project-label">Project</InputLabel>
              <Select
                labelId="dialog-project-label"
                label="Project"
                value={dialogProjectId}
                onChange={(event) => setDialogProjectId(String(event.target.value))}
              >
                {projects.map((item) => (
                  <MenuItem key={item.id} value={item.id}>
                    {item.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <ToggleButtonGroup
              exclusive
              value={dialogPublishMode}
              onChange={(_event, value: 'now' | 'schedule' | null) => {
                if (value) setDialogPublishMode(value);
              }}
            >
              <ToggleButton value="now">Publish now</ToggleButton>
              <ToggleButton value="schedule">Schedule</ToggleButton>
            </ToggleButtonGroup>
            {dialogPublishMode === 'schedule' ? (
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                <TextField
                  label="Date"
                  type="date"
                  fullWidth
                  value={dialogScheduledDate}
                  onChange={(event) => setDialogScheduledDate(event.target.value)}
                  inputProps={{ min: minScheduleDate }}
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  label="Time"
                  type="time"
                  fullWidth
                  value={dialogScheduledTime}
                  onChange={(event) => setDialogScheduledTime(event.target.value)}
                  inputProps={
                    dialogTimeMinForSelectedDate ? { min: dialogTimeMinForSelectedDate } : undefined
                  }
                  InputLabelProps={{ shrink: true }}
                />
              </Stack>
            ) : null}
            {selectedDraft?.platform === 'facebook' ? (
              <FormControl fullWidth>
                <InputLabel id="dialog-fb-page-label">Facebook page</InputLabel>
                <Select
                  labelId="dialog-fb-page-label"
                  label="Facebook page"
                  value={dialogPageId}
                  onChange={(event) => setDialogPageId(String(event.target.value))}
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
            <Box
              sx={{
                px: 1.25,
                py: 1,
                borderRadius: 1.5,
                border: '1px solid #c8d8ea',
                bgcolor: '#edf3fb',
                color: '#2a4464',
                fontSize: '0.88rem',
              }}
            >
              {dialogPublishMode === 'now'
                ? 'This draft will be published immediately.'
                : dialogScheduleSummaryText}
            </Box>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button onClick={() => setScheduleDialogOpen(false)}>Close</Button>
          <Button variant="contained" onClick={() => void handleScheduleFromDraft()} disabled={submitting}>
            {submitting ? 'Submitting...' : 'Create Schedule'}
          </Button>
        </DialogActions>
      </Dialog>

      <ProfileDialog open={profileDialogOpen} onClose={() => setProfileDialogOpen(false)} />
      <ProjectSettingsDialog open={projectSettingsOpen} onClose={() => setProjectSettingsOpen(false)} />
    </Box>
  );
};

export default AutoPostFeature;
