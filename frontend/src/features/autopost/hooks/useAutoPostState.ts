import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ensureAuthenticatedAccessToken, meApi } from '@/features/auth/api/authApi';
import { startFacebookConnectApi } from '@/features/profile/api/facebookApi';
import { startLinkedInConnectApi } from '@/features/profile/api/linkedinApi';
import {
  type AutopostCreateJobPayload,
  cancelAutopostJobApi,
  type AutopostCreateJobError,
  createAutopostJobApi,
  getFacebookPagesApi,
  getProjectHistoryApi,
  getProjectsApi,
  listAutopostJobsApi,
  retryAutopostJobApi,
} from '@/features/workspace/api/workspaceApi';
import type {
  AutopostJobItem,
  AutopostPlatform,
  AutopostSourceMode,
  ContentSocialPost,
  FacebookPageOption,
  ProjectItem,
  RunItem,
} from '@/features/workspace/types';
import { getActiveProjectId, setActiveProjectId } from '@/features/workspace/projectStorage';
import type { UserItem } from '@/features/users/api/userApi';
import { extractContentPlanFromRun } from '@/features/workspace/historyUtils';
import { buildSocialPostText } from '@/features/workspace/socialTextUtils';

export type AutoPostFeedFilter = 'all' | 'linkedin' | 'facebook' | 'scheduled' | 'unscheduled';

export type CurrentChatDraftItem = {
  platform: AutopostPlatform;
  content: string;
  updatedAt: string;
  runId: string;
  source: 'chat';
  projectId: string;
  projectName: string;
};

export type AutopostJobViewItem = AutopostJobItem & {
  project_name: string;
};

const PENDING_CONNECT_STORAGE_KEY = 'autopost.pending.create_job.v1';
const PENDING_CONNECT_MAX_AGE_MS = 30 * 60 * 1000;
const JOB_POLL_INTERVAL_MS = 5000;
const ACTIVE_JOB_STATUSES = new Set([
  'QUEUED',
  'GENERATING',
  'READY',
  'SCHEDULED',
  'PUBLISHING',
  'PUBLISH_UNKNOWN',
]);

export type AutoPostConnectPrompt = {
  message: string;
  platform: AutopostPlatform | null;
  connectUrl: string | null;
  connectReason: string | null;
};

type AutoPostState = {
  user: UserItem | null;
  project: ProjectItem | null;
  projects: ProjectItem[];
  activeProjectId: string | null;
  jobs: AutopostJobViewItem[];
  currentChatDrafts: CurrentChatDraftItem[];
  feedFilter: AutoPostFeedFilter;
  loading: boolean;
  submitting: boolean;
  error: string | null;
  connectPrompt: AutoPostConnectPrompt | null;
  keyword: string;
  platform: AutopostPlatform;
  publishMode: 'now' | 'schedule';
  scheduledDate: string;
  scheduledTime: string;
  pageId: string;
  scheduleProjectId: string;
  dialogProjectId: string;
  facebookPages: FacebookPageOption[];
  facebookPagesLoading: boolean;
  setFeedFilter: (value: AutoPostFeedFilter) => void;
  setKeyword: (value: string) => void;
  setPlatform: (value: AutopostPlatform) => void;
  setPublishMode: (value: 'now' | 'schedule') => void;
  setScheduledDate: (value: string) => void;
  setScheduledTime: (value: string) => void;
  setPageId: (value: string) => void;
  setScheduleProjectId: (value: string) => void;
  setDialogProjectId: (value: string) => void;
  dismissConnectPrompt: () => void;
  startSocialConnect: (onMissingUrl?: () => void) => Promise<void>;
  submitJob: () => Promise<void>;
  reloadJobs: () => Promise<void>;
  retryJob: (jobId: string) => Promise<void>;
  cancelJob: (jobId: string) => Promise<void>;
  scheduleFromContent: (payload: {
    projectId: string;
    platform: AutopostPlatform;
    content: string;
    publishMode: 'now' | 'schedule';
    scheduledDate: string;
    scheduledTime: string;
    pageId?: string;
  }) => Promise<boolean>;
  needsReconnect: boolean;
  switchProject: (projectId: string) => void;
};

const toDateInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

const toTimeInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const normalizePlatform = (value: string): AutopostPlatform | null => {
  const normalized = value.trim().toLowerCase();
  if (normalized === 'linkedin') return 'linkedin';
  if (normalized === 'facebook') return 'facebook';
  return null;
};

const getRunTimestamp = (run: RunItem): string => {
  return run.finished_at || run.started_at || run.createdAt || new Date().toISOString();
};

const buildDraftFromPost = (
  run: RunItem,
  post: ContentSocialPost,
  project: ProjectItem,
): CurrentChatDraftItem | null => {
  const platform = normalizePlatform(post.platform);
  if (!platform) return null;
  const text = buildSocialPostText(post).trim();
  if (!text) return null;
  return {
    platform,
    content: text,
    updatedAt: getRunTimestamp(run),
    runId: run.id,
    source: 'chat',
    projectId: project.id,
    projectName: project.name,
  };
};

const deriveLatestChatDraftsForProject = (
  runs: RunItem[],
  project: ProjectItem,
): CurrentChatDraftItem[] => {
  const byPlatform: Partial<Record<AutopostPlatform, CurrentChatDraftItem>> = {};
  for (const run of runs) {
    const trigger = String(run.request_payload?.trigger || '').toLowerCase();
    if (trigger === 'autopost' || trigger === 'autopost_publish' || trigger === 'autopost_manual') {
      continue;
    }
    const snapshot = extractContentPlanFromRun(run);
    if (!snapshot) continue;
    for (const post of snapshot.social_posts) {
      const platform = normalizePlatform(post.platform);
      if (!platform || byPlatform[platform]) continue;
      const draft = buildDraftFromPost(run, post, project);
      if (draft) {
        byPlatform[platform] = draft;
      }
    }
    if (byPlatform.linkedin && byPlatform.facebook) break;
  }
  return [byPlatform.linkedin, byPlatform.facebook].filter(
    (item): item is CurrentChatDraftItem => Boolean(item),
  );
};

const isAutopostCreateJobPayload = (value: unknown): value is AutopostCreateJobPayload => {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Record<string, unknown>;
  const platform = String(candidate.platform || '').toLowerCase();
  const projectId = String(candidate.project_id || '').trim();
  const scheduledAt = String(candidate.scheduled_at || '').trim();
  if (!projectId || !scheduledAt) return false;
  if (platform !== 'linkedin' && platform !== 'facebook') return false;
  return true;
};

const persistPendingConnectPayload = (payload: AutopostCreateJobPayload) => {
  try {
    sessionStorage.setItem(
      PENDING_CONNECT_STORAGE_KEY,
      JSON.stringify({
        created_at: Date.now(),
        payload,
      }),
    );
  } catch {
    // no-op
  }
};

const readPendingConnectPayload = (): AutopostCreateJobPayload | null => {
  try {
    const raw = sessionStorage.getItem(PENDING_CONNECT_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as {
      created_at?: unknown;
      payload?: unknown;
    };
    const createdAt = Number(parsed.created_at || 0);
    if (!Number.isFinite(createdAt) || Date.now() - createdAt > PENDING_CONNECT_MAX_AGE_MS) {
      sessionStorage.removeItem(PENDING_CONNECT_STORAGE_KEY);
      return null;
    }
    if (!isAutopostCreateJobPayload(parsed.payload)) {
      sessionStorage.removeItem(PENDING_CONNECT_STORAGE_KEY);
      return null;
    }
    return parsed.payload;
  } catch {
    return null;
  }
};

const clearPendingConnectPayload = () => {
  try {
    sessionStorage.removeItem(PENDING_CONNECT_STORAGE_KEY);
  } catch {
    // no-op
  }
};

const consumeConnectedQueryFlags = (): boolean => {
  try {
    const url = new URL(window.location.href);
    const hasLinkedinConnected = url.searchParams.get('linkedin') === 'connected';
    const hasFacebookConnected = url.searchParams.get('facebook') === 'connected';
    const hasConnectedFlag = hasLinkedinConnected || hasFacebookConnected;
    if (!hasConnectedFlag) return false;

    url.searchParams.delete('linkedin');
    url.searchParams.delete('facebook');
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState({}, '', nextUrl);
    return true;
  } catch {
    return false;
  }
};

export const useAutoPostState = (): AutoPostState => {
  const navigate = useNavigate();
  const resumeAttemptedRef = useRef(false);
  const [user, setUser] = useState<UserItem | null>(null);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(null);
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [jobs, setJobs] = useState<AutopostJobViewItem[]>([]);
  const [currentChatDrafts, setCurrentChatDrafts] = useState<CurrentChatDraftItem[]>([]);
  const [feedFilter, setFeedFilter] = useState<AutoPostFeedFilter>('all');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectPrompt, setConnectPrompt] = useState<AutoPostConnectPrompt | null>(null);
  const [keyword, setKeyword] = useState('');
  const [platform, setPlatform] = useState<AutopostPlatform>('linkedin');
  const [publishMode, setPublishMode] = useState<'now' | 'schedule'>('now');
  const minScheduledAt = new Date(Date.now() + 30 * 60 * 1000);
  const [scheduledDate, setScheduledDate] = useState(toDateInput(minScheduledAt));
  const [scheduledTime, setScheduledTime] = useState(toTimeInput(minScheduledAt));
  const [pageId, setPageId] = useState('');
  const [scheduleProjectId, setScheduleProjectId] = useState('');
  const [dialogProjectId, setDialogProjectId] = useState('');
  const [facebookPages, setFacebookPages] = useState<FacebookPageOption[]>([]);
  const [facebookPagesLoading, setFacebookPagesLoading] = useState(false);

  const projectMap = useMemo(() => {
    const map = new Map<string, ProjectItem>();
    for (const item of projects) {
      map.set(item.id, item);
    }
    return map;
  }, [projects]);

  const resolveScheduledAt = useCallback(
    (mode: 'now' | 'schedule', dateText: string, timeText: string): Date | null => {
      if (mode === 'now') return new Date();
      const parsed = new Date(`${dateText}T${timeText}`);
      if (Number.isNaN(parsed.getTime())) return null;
      return parsed;
    },
    [],
  );

  const dismissConnectPrompt = useCallback(() => {
    setConnectPrompt(null);
  }, []);

  const startSocialConnect = useCallback(async (onMissingUrl?: () => void) => {
    const platform = connectPrompt?.platform;
    if (platform === 'linkedin' || platform === 'facebook') {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }
      try {
        const returnTo = `${window.location.pathname}${window.location.search}`;
        const response = platform === 'linkedin'
          ? await startLinkedInConnectApi(accessToken, returnTo)
          : await startFacebookConnectApi(accessToken, returnTo);
        const authorizeUrl = String(response.authorize_url || '').trim();
        if (authorizeUrl) {
          window.location.href = authorizeUrl;
          return;
        }
      } catch {
        // Fall back to connectUrl from autopost error payload.
      }
    }
    const url = (connectPrompt?.connectUrl || '').trim();
    if (url) {
      window.location.href = url;
      return;
    }
    onMissingUrl?.();
  }, [connectPrompt, navigate]);

  const handleCreateJobError = useCallback((
    submitError: unknown,
    fallbackMessage: string,
    fallbackPlatform: AutopostPlatform,
    pendingPayload?: AutopostCreateJobPayload,
  ) => {
    const structuredError = submitError as AutopostCreateJobError;
    const message = submitError instanceof Error ? submitError.message : fallbackMessage;
    if (structuredError?.connectRequired) {
      setError(null);
      setConnectPrompt({
        message,
        platform: structuredError.connectPlatform || fallbackPlatform,
        connectUrl: structuredError.connectUrl || null,
        connectReason: structuredError.connectReason || null,
      });
      if (pendingPayload) {
        persistPendingConnectPayload(pendingPayload);
      }
      return;
    }
    setError(message);
    setConnectPrompt(null);
    clearPendingConnectPayload();
  }, []);

  const loadProjectDatasets = useCallback(async (
    accessToken: string,
    projectList: ProjectItem[],
  ): Promise<{ jobs: AutopostJobViewItem[]; drafts: CurrentChatDraftItem[] }> => {
    const allJobs: AutopostJobViewItem[] = [];
    const allDrafts: CurrentChatDraftItem[] = [];

    await Promise.all(
      projectList.map(async (projectItem) => {
        const [projectJobs, runs] = await Promise.all([
          listAutopostJobsApi(accessToken, projectItem.id),
          getProjectHistoryApi(accessToken, projectItem.id),
        ]);

        for (const job of projectJobs) {
          allJobs.push({ ...job, project_name: projectItem.name });
        }

        allDrafts.push(...deriveLatestChatDraftsForProject(runs, projectItem));
      }),
    );

    allJobs.sort((a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime());
    allDrafts.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

    return { jobs: allJobs, drafts: allDrafts };
  }, []);

  const refreshAggregatedData = useCallback(async (accessToken: string, projectList: ProjectItem[]) => {
    const datasets = await loadProjectDatasets(accessToken, projectList);
    setJobs(datasets.jobs);
    setCurrentChatDrafts(datasets.drafts);
  }, [loadProjectDatasets]);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }

      const me = await meApi(accessToken);
      setUser(me);

      const projectList = await getProjectsApi(accessToken);
      setProjects(projectList);
      if (!projectList.length) {
        navigate({ to: '/welcome' });
        return;
      }

      let resolvedActiveProjectId = getActiveProjectId();
      if (!resolvedActiveProjectId || !projectList.some((item) => item.id === resolvedActiveProjectId)) {
        resolvedActiveProjectId = projectList[0].id;
        setActiveProjectId(resolvedActiveProjectId);
      }

      setActiveProjectIdState(resolvedActiveProjectId);
      const activeProject =
        projectList.find((item) => item.id === resolvedActiveProjectId) || projectList[0];
      setProject(activeProject);

      setScheduleProjectId((prev) => {
        if (prev && projectList.some((item) => item.id === prev)) {
          return prev;
        }
        return activeProject.id;
      });
      setDialogProjectId((prev) => {
        if (prev && projectList.some((item) => item.id === prev)) {
          return prev;
        }
        return activeProject.id;
      });

      await refreshAggregatedData(accessToken, projectList);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load auto-post workspace.');
    } finally {
      setLoading(false);
    }
  }, [navigate, refreshAggregatedData]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    const refresh = () => {
      void loadWorkspace();
    };
    window.addEventListener('project-updated', refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener('project-updated', refresh);
      window.removeEventListener('storage', refresh);
    };
  }, [loadWorkspace]);

  useEffect(() => {
    const loadPages = async () => {
      if (platform !== 'facebook') {
        setFacebookPages([]);
        return;
      }
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) return;
      setFacebookPagesLoading(true);
      try {
        const pages = await getFacebookPagesApi(accessToken);
        setFacebookPages(pages);
        if (!pageId && pages.length) {
          setPageId(pages[0].id);
        }
      } catch (pageError) {
        setError(pageError instanceof Error ? pageError.message : 'Failed to load Facebook pages.');
      } finally {
        setFacebookPagesLoading(false);
      }
    };
    void loadPages();
  }, [pageId, platform]);

  const switchProject = useCallback((projectId: string) => {
    const nextProjectId = projectId.trim();
    if (!nextProjectId || nextProjectId === activeProjectId) {
      return;
    }
    const selectedProject = projectMap.get(nextProjectId) || null;
    setActiveProjectId(nextProjectId);
    setActiveProjectIdState(nextProjectId);
    setProject(selectedProject);
    setScheduleProjectId(nextProjectId);
  }, [activeProjectId, projectMap]);

  const reloadJobs = useCallback(async () => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken || !projects.length) return;
    await refreshAggregatedData(accessToken, projects);
  }, [projects, refreshAggregatedData]);

  const submitJob = useCallback(async () => {
    const normalizedKeyword = keyword.trim();
    if (!normalizedKeyword) {
      setError('Keyword is required.');
      return;
    }

    const targetProjectId = scheduleProjectId.trim();
    if (!targetProjectId || !projectMap.has(targetProjectId)) {
      setError('Please select a valid project.');
      return;
    }

    const parsedTime = resolveScheduledAt(publishMode, scheduledDate, scheduledTime);
    if (publishMode === 'schedule') {
      if (!parsedTime) {
        setError('Scheduled time is invalid.');
        return;
      }
      if (parsedTime.getTime() < Date.now() + 30 * 60 * 1000) {
        setError('Scheduled time must be at least 30 minutes from now.');
        return;
      }
    }

    if (platform === 'facebook' && !pageId.trim()) {
      setError('Please select a Facebook page.');
      return;
    }

    setSubmitting(true);
    setError(null);
    setConnectPrompt(null);
    try {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }
      const requestPayload: AutopostCreateJobPayload = {
        project_id: targetProjectId,
        platform,
        keyword: normalizedKeyword,
        scheduled_at: (parsedTime || new Date()).toISOString(),
        publish_mode: publishMode,
        page_id: platform === 'facebook' ? pageId : undefined,
        source_mode: 'keyword',
      };
      await createAutopostJobApi(accessToken, requestPayload);
      clearPendingConnectPayload();
      setKeyword('');
      switchProject(targetProjectId);
      await refreshAggregatedData(accessToken, projects);
    } catch (submitError) {
      const requestPayload: AutopostCreateJobPayload = {
        project_id: targetProjectId,
        platform,
        keyword: normalizedKeyword,
        scheduled_at: (parsedTime || new Date()).toISOString(),
        publish_mode: publishMode,
        page_id: platform === 'facebook' ? pageId : undefined,
        source_mode: 'keyword',
      };
      handleCreateJobError(
        submitError,
        'Failed to create auto-post job.',
        platform,
        requestPayload,
      );
    } finally {
      setSubmitting(false);
    }
  }, [
    keyword,
    navigate,
    pageId,
    platform,
    projectMap,
    projects,
    publishMode,
    refreshAggregatedData,
    resolveScheduledAt,
    scheduleProjectId,
    scheduledDate,
    scheduledTime,
    switchProject,
    handleCreateJobError,
  ]);

  const scheduleFromContent = useCallback(async (
    payload: {
      projectId: string;
      platform: AutopostPlatform;
      content: string;
      publishMode: 'now' | 'schedule';
      scheduledDate: string;
      scheduledTime: string;
      pageId?: string;
    },
  ): Promise<boolean> => {
    const normalizedContent = payload.content.trim();
    if (!normalizedContent) {
      setError('Content is required.');
      return false;
    }

    const targetProjectId = payload.projectId.trim();
    if (!targetProjectId || !projectMap.has(targetProjectId)) {
      setError('Please select a valid project.');
      return false;
    }

    const resolvedTime = resolveScheduledAt(
      payload.publishMode,
      payload.scheduledDate,
      payload.scheduledTime,
    );
    if (payload.publishMode === 'schedule') {
      if (!resolvedTime) {
        setError('Scheduled time is invalid.');
        return false;
      }
      if (resolvedTime.getTime() < Date.now() + 30 * 60 * 1000) {
        setError('Scheduled time must be at least 30 minutes from now.');
        return false;
      }
    }

    if (payload.platform === 'facebook' && !(payload.pageId || '').trim()) {
      setError('Please select a Facebook page.');
      return false;
    }

    setSubmitting(true);
    setError(null);
    setConnectPrompt(null);
    try {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return false;
      }
      const sourceMode: AutopostSourceMode = 'content';
      const requestPayload: AutopostCreateJobPayload = {
        project_id: targetProjectId,
        platform: payload.platform,
        scheduled_at: (resolvedTime || new Date()).toISOString(),
        publish_mode: payload.publishMode,
        page_id: payload.platform === 'facebook' ? payload.pageId : undefined,
        source_mode: sourceMode,
        content: normalizedContent,
      };
      await createAutopostJobApi(accessToken, requestPayload);
      clearPendingConnectPayload();
      switchProject(targetProjectId);
      setScheduleProjectId(targetProjectId);
      await refreshAggregatedData(accessToken, projects);
      return true;
    } catch (submitError) {
      const sourceMode: AutopostSourceMode = 'content';
      const requestPayload: AutopostCreateJobPayload = {
        project_id: targetProjectId,
        platform: payload.platform,
        scheduled_at: (resolvedTime || new Date()).toISOString(),
        publish_mode: payload.publishMode,
        page_id: payload.platform === 'facebook' ? payload.pageId : undefined,
        source_mode: sourceMode,
        content: normalizedContent,
      };
      handleCreateJobError(
        submitError,
        'Failed to create auto-post job from content.',
        payload.platform,
        requestPayload,
      );
      return false;
    } finally {
      setSubmitting(false);
    }
  }, [
    navigate,
    projectMap,
    projects,
    refreshAggregatedData,
    resolveScheduledAt,
    switchProject,
    handleCreateJobError,
  ]);

  const resumePendingConnectSubmission = useCallback(async () => {
    if (resumeAttemptedRef.current) {
      return;
    }
    if (!consumeConnectedQueryFlags()) {
      return;
    }
    const pendingPayload = readPendingConnectPayload();
    if (!pendingPayload) {
      return;
    }
    resumeAttemptedRef.current = true;
    setSubmitting(true);
    setError(null);
    setConnectPrompt(null);
    try {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }
      await createAutopostJobApi(accessToken, pendingPayload);
      clearPendingConnectPayload();
      setKeyword('');
      switchProject(pendingPayload.project_id);
      setScheduleProjectId(pendingPayload.project_id);
      await refreshAggregatedData(accessToken, projects);
    } catch (submitError) {
      handleCreateJobError(
        submitError,
        'Failed to resume auto-post after social connection.',
        pendingPayload.platform,
        pendingPayload,
      );
    } finally {
      setSubmitting(false);
    }
  }, [
    handleCreateJobError,
    navigate,
    projects,
    refreshAggregatedData,
    switchProject,
  ]);

  useEffect(() => {
    if (loading || !projects.length) {
      return;
    }
    void resumePendingConnectSubmission();
  }, [loading, projects.length, resumePendingConnectSubmission]);

  const retryJob = useCallback(async (jobId: string) => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) return;
    try {
      await retryAutopostJobApi(accessToken, jobId);
      await refreshAggregatedData(accessToken, projects);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : 'Failed to retry job.');
    }
  }, [projects, refreshAggregatedData]);

  const cancelJob = useCallback(async (jobId: string) => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) return;
    try {
      await cancelAutopostJobApi(accessToken, jobId);
      await refreshAggregatedData(accessToken, projects);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : 'Failed to cancel job.');
    }
  }, [projects, refreshAggregatedData]);

  const needsReconnect = useMemo(
    () => jobs.some((job) => job.status === 'NEEDS_RECONNECT'),
    [jobs],
  );

  const hasActiveJobs = useMemo(
    () => jobs.some((job) => ACTIVE_JOB_STATUSES.has(job.status)),
    [jobs],
  );

  useEffect(() => {
    if (!hasActiveJobs || !projects.length) {
      return;
    }

    let cancelled = false;
    const poll = async () => {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken || cancelled) return;
      try {
        await refreshAggregatedData(accessToken, projects);
      } catch {
        // ignore transient polling errors
      }
    };

    const intervalId = window.setInterval(() => {
      void poll();
    }, JOB_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [hasActiveJobs, projects, refreshAggregatedData]);

  return {
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
    reloadJobs,
    retryJob,
    cancelJob,
    scheduleFromContent,
    needsReconnect,
    switchProject,
  };
};
