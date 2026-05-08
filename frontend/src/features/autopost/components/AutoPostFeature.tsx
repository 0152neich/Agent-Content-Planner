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
  IconButton,
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
import ManageSearchRoundedIcon from '@mui/icons-material/ManageSearchRounded';
import MoreHorizRoundedIcon from '@mui/icons-material/MoreHorizRounded';
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
import type { AutoPostFeedFilter, CurrentChatDraftItem } from '../hooks/useAutoPostState';

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
    project,
    projects,
    activeProjectId,
    jobs,
    currentChatDrafts,
    feedFilter,
    loading,
    submitting,
    error,
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
    submitJob,
    retryJob,
    cancelJob,
    scheduleFromContent,
    needsReconnect,
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
                    PROJECT
                  </Typography>
                  <FormControl fullWidth>
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
                  : scheduleSummaryText}
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

          <Paper
            sx={{
              mb: 3,
              borderRadius: 2.5,
              border: '1px solid #d5e0ec',
              p: { xs: 1.5, md: 2 },
              background: 'linear-gradient(180deg, rgba(255,255,255,0.95) 0%, rgba(246,251,255,0.9) 100%)',
            }}
          >
            <Stack spacing={1.4}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'flex-start', sm: 'center' }}>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                  Feed Filter
                </Typography>
                <Typography sx={{ fontSize: '0.84rem', color: '#5f6f84' }}>
                  Lọc nhanh bài nháp và lịch đăng theo nền tảng hoặc trạng thái.
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {FEED_FILTER_OPTIONS.map(({ value, label }) => (
                  <Chip
                    key={value}
                    label={label}
                    clickable
                    onClick={() => setFeedFilter(value)}
                    color={feedFilter === value ? 'primary' : 'default'}
                    variant={feedFilter === value ? 'filled' : 'outlined'}
                    sx={{
                      borderRadius: 999,
                      px: 0.4,
                      fontWeight: feedFilter === value ? 700 : 500,
                      bgcolor: feedFilter === value ? '#dbe9f9' : '#f5f9ff',
                      color: feedFilter === value ? '#10355f' : '#48617d',
                      borderColor: '#c1d3e8',
                      '& .MuiChip-label': { px: 1.2 },
                    }}
                  />
                ))}
              </Stack>
            </Stack>
          </Paper>

          <Paper
            sx={{
              mb: 3,
              borderRadius: 2.5,
              border: '1px solid #d5e0ec',
              p: { xs: 1.5, md: 2 },
              background: 'rgba(255,255,255,0.82)',
            }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Typography variant="h6" sx={{ fontWeight: 700 }}>
                Current Chat Drafts
              </Typography>
              <Chip
                size="small"
                label={`${filteredDrafts.length} draft${filteredDrafts.length === 1 ? '' : 's'}`}
                variant="outlined"
                sx={{ borderColor: '#c1d3e8', color: '#355373', fontWeight: 600 }}
              />
            </Stack>
            {loading ? (
              <CircularProgress size={20} sx={{ mb: 1 }} />
            ) : filteredDrafts.length === 0 ? (
              <Box
                sx={{
                  border: '1px dashed #c9d6e3',
                  borderRadius: 2,
                  px: 2,
                  py: 3,
                  color: 'text.secondary',
                }}
              >
                <Typography color="text.secondary">No current chat drafts for this filter.</Typography>
              </Box>
            ) : (
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', md: 'repeat(3, minmax(0, 1fr))' },
                  gap: 1.5,
                }}
              >
                {filteredDrafts.map((draft) => (
                  <Paper
                    key={`${draft.projectId}-${draft.platform}-${draft.runId}`}
                    onClick={() => openDraftPreview(draft)}
                    sx={{
                      minHeight: 220,
                      p: 1.5,
                      borderRadius: 2,
                      border: '1px solid #d2deeb',
                      background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,252,255,0.94) 100%)',
                      cursor: 'pointer',
                      position: 'relative',
                      overflow: 'hidden',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 1,
                      transition: 'transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease',
                      '&:hover': {
                        transform: 'translateY(-1px)',
                        boxShadow: '0 10px 22px rgba(23, 61, 96, 0.12)',
                        borderColor: '#a9c0da',
                      },
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ pr: 4.5, minWidth: 0, flexWrap: 'nowrap' }}>
                      <Chip
                        size="small"
                        label={draft.platform.toUpperCase()}
                        variant="outlined"
                        sx={{
                          height: 24,
                          bgcolor: '#ffffff',
                          borderColor: '#9db7d3',
                          color: '#24517e',
                          fontWeight: 700,
                          '& .MuiChip-label': { px: 1 },
                        }}
                      />
                      <Chip
                        size="small"
                        label={draft.projectName}
                        variant="outlined"
                        sx={{
                          height: 24,
                          minWidth: 0,
                          maxWidth: '100%',
                          borderColor: '#b9cce0',
                          color: '#4b6685',
                          '& .MuiChip-label': {
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            px: 1,
                          },
                        }}
                      />
                    </Stack>
                    <Typography variant="caption" color="text.secondary">
                      Updated {formatDate(draft.updatedAt)}
                    </Typography>
                    <Typography
                      sx={{
                        color: '#20364f',
                        wordBreak: 'break-word',
                        display: '-webkit-box',
                        overflow: 'hidden',
                        WebkitLineClamp: 6,
                        WebkitBoxOrient: 'vertical',
                        lineHeight: 1.46,
                        fontSize: '0.95rem',
                        flex: 1,
                      }}
                    >
                      {toDraftExcerpt(draft.content)}
                    </Typography>
                    <Typography sx={{ fontSize: '0.8rem', color: '#4f647f', fontWeight: 600 }}>
                      Click to preview and schedule
                    </Typography>
                    <IconButton
                      size="small"
                      onClick={(event) => openDraftMenu(event, draft)}
                      sx={{
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        color: '#5a7089',
                        bgcolor: 'rgba(232,241,251,0.92)',
                        '&:hover': { bgcolor: '#dceaf8' },
                      }}
                    >
                      <MoreHorizRoundedIcon fontSize="small" />
                    </IconButton>
                  </Paper>
                ))}
              </Box>
            )}
          </Paper>

          <Paper
            sx={{
              borderRadius: 2.5,
              border: '1px solid #d5e0ec',
              p: { xs: 1.5, md: 2 },
              background: 'rgba(255,255,255,0.82)',
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5 }}>
              AutoPost Jobs Timeline
            </Typography>
            {loading ? (
              <CircularProgress size={20} />
            ) : filteredJobs.length === 0 ? (
              <Box
                sx={{
                  border: '1px dashed #c9d6e3',
                  borderRadius: 2,
                  px: 3,
                  py: 6,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 1.5,
                  color: 'text.secondary',
                }}
              >
                <ScheduleOutlinedIcon sx={{ fontSize: 52, color: '#7f8ea3' }} />
                <Typography color="text.secondary">No auto-post jobs yet.</Typography>
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
                        <Typography sx={{ fontWeight: 700 }}>{job.keyword}</Typography>
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
