import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ensureAuthenticatedAccessToken, meApi } from '@/features/auth/api/authApi';
import {
  cancelAutopostJobApi,
  createAutopostJobApi,
  getFacebookPagesApi,
  getProjectByIdApi,
  getProjectsApi,
  listAutopostJobsApi,
  retryAutopostJobApi,
} from '@/features/workspace/api/workspaceApi';
import type {
  AutopostJobItem,
  AutopostPlatform,
  FacebookPageOption,
  ProjectItem,
} from '@/features/workspace/types';
import { getActiveProjectId, setActiveProjectId } from '@/features/workspace/projectStorage';
import type { UserItem } from '@/features/users/api/userApi';

type AutoPostState = {
  user: UserItem | null;
  project: ProjectItem | null;
  jobs: AutopostJobItem[];
  loading: boolean;
  submitting: boolean;
  error: string | null;
  keyword: string;
  platform: AutopostPlatform;
  publishMode: 'now' | 'schedule';
  scheduledDate: string;
  scheduledTime: string;
  pageId: string;
  facebookPages: FacebookPageOption[];
  facebookPagesLoading: boolean;
  setKeyword: (value: string) => void;
  setPlatform: (value: AutopostPlatform) => void;
  setPublishMode: (value: 'now' | 'schedule') => void;
  setScheduledDate: (value: string) => void;
  setScheduledTime: (value: string) => void;
  setPageId: (value: string) => void;
  submitJob: () => Promise<void>;
  reloadJobs: () => Promise<void>;
  retryJob: (jobId: string) => Promise<void>;
  cancelJob: (jobId: string) => Promise<void>;
  needsReconnect: boolean;
};

const toDateInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

const toTimeInput = (date: Date): string => {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const useAutoPostState = (): AutoPostState => {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserItem | null>(null);
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [jobs, setJobs] = useState<AutopostJobItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [keyword, setKeyword] = useState('');
  const [platform, setPlatform] = useState<AutopostPlatform>('linkedin');
  const [publishMode, setPublishMode] = useState<'now' | 'schedule'>('now');
  const minScheduledAt = new Date(Date.now() + 30 * 60 * 1000);
  const [scheduledDate, setScheduledDate] = useState(toDateInput(minScheduledAt));
  const [scheduledTime, setScheduledTime] = useState(toTimeInput(minScheduledAt));
  const [pageId, setPageId] = useState('');
  const [facebookPages, setFacebookPages] = useState<FacebookPageOption[]>([]);
  const [facebookPagesLoading, setFacebookPagesLoading] = useState(false);

  const loadJobs = useCallback(async (accessToken: string, projectId: string) => {
    const data = await listAutopostJobsApi(accessToken, projectId);
    setJobs(data);
  }, []);

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

      let activeProjectId = getActiveProjectId();
      const projects = await getProjectsApi(accessToken);
      if (!projects.length) {
        navigate({ to: '/welcome' });
        return;
      }
      if (!activeProjectId || !projects.some((item) => item.id === activeProjectId)) {
        activeProjectId = projects[0].id;
        setActiveProjectId(activeProjectId);
      }

      const selectedProject = await getProjectByIdApi(accessToken, activeProjectId);
      setProject(selectedProject);
      await loadJobs(accessToken, selectedProject.id);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load auto-post workspace.');
    } finally {
      setLoading(false);
    }
  }, [loadJobs, navigate]);

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

  const reloadJobs = useCallback(async () => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken || !project?.id) return;
    await loadJobs(accessToken, project.id);
  }, [loadJobs, project?.id]);

  const submitJob = useCallback(async () => {
    const normalizedKeyword = keyword.trim();
    if (!normalizedKeyword) {
      setError('Keyword is required.');
      return;
    }
    const parsedTime = new Date(`${scheduledDate}T${scheduledTime}`);
    if (publishMode === 'schedule') {
      if (Number.isNaN(parsedTime.getTime())) {
        setError('Scheduled time is invalid.');
        return;
      }
      if (parsedTime.getTime() < Date.now() + 30 * 60 * 1000) {
        setError('Scheduled time must be at least 30 minutes from now.');
        return;
      }
    }
    if (!project?.id) {
      setError('No active project found.');
      return;
    }
    if (platform === 'facebook' && !pageId.trim()) {
      setError('Please select a Facebook page.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }
      await createAutopostJobApi(accessToken, {
        project_id: project.id,
        platform,
        keyword: normalizedKeyword,
        scheduled_at: (publishMode === 'now' ? new Date() : parsedTime).toISOString(),
        publish_mode: publishMode,
        page_id: platform === 'facebook' ? pageId : undefined,
      });
      setKeyword('');
      await loadJobs(accessToken, project.id);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to create auto-post job.');
    } finally {
      setSubmitting(false);
    }
  }, [keyword, navigate, pageId, platform, project?.id, publishMode, scheduledDate, scheduledTime, loadJobs]);

  const retryJob = useCallback(async (jobId: string) => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken || !project?.id) return;
    try {
      await retryAutopostJobApi(accessToken, jobId);
      await loadJobs(accessToken, project.id);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : 'Failed to retry job.');
    }
  }, [loadJobs, project?.id]);

  const cancelJob = useCallback(async (jobId: string) => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken || !project?.id) return;
    try {
      await cancelAutopostJobApi(accessToken, jobId);
      await loadJobs(accessToken, project.id);
    } catch (jobError) {
      setError(jobError instanceof Error ? jobError.message : 'Failed to cancel job.');
    }
  }, [loadJobs, project?.id]);

  const needsReconnect = useMemo(
    () => jobs.some((job) => job.status === 'NEEDS_RECONNECT'),
    [jobs],
  );

  return {
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
    reloadJobs,
    retryJob,
    cancelJob,
    needsReconnect,
  };
};
