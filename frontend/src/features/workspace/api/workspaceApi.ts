import {
  API_BASE_URL,
  type ApiEnvelope,
  requestEnvelope,
  requestJson,
  withAuthHeaders,
} from '@/lib/apiClient';
import type {
  ContentPlanData,
  ConversationMessageCreateResult,
  FacebookPageOption,
  ConversationItem,
  MessageItem,
  ProjectItem,
  RunItem,
  SocialPublishPlatform,
  SocialPublishResult,
  AutopostJobItem,
  AutopostPlatform,
} from '../types';

export const getHealthApi = async (): Promise<{ status: string }> =>
  requestJson<{ status: string; message?: string }>('/health', {
    headers: { 'Content-Type': 'application/json' },
  }).then((data) => ({ status: data.status }));

export const getProjectsApi = async (accessToken: string): Promise<ProjectItem[]> =>
  requestEnvelope<{ projects: ProjectItem[] }>('/projects', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  }).then((data) => data.projects);

export const createProjectApi = async (
  accessToken: string,
  payload: { name: string; source_url?: string | null; description?: string | null; status?: string },
): Promise<ProjectItem> =>
  requestEnvelope<ProjectItem>('/projects', {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const getProjectByIdApi = async (
  accessToken: string,
  projectId: string,
): Promise<ProjectItem> =>
  requestEnvelope<ProjectItem>(`/projects/${projectId}`, {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const updateProjectApi = async (
  accessToken: string,
  projectId: string,
  payload: { name?: string; source_url?: string | null; description?: string | null; status?: string },
): Promise<ProjectItem> =>
  requestEnvelope<ProjectItem>(`/projects/${projectId}`, {
    method: 'PUT',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const deleteProjectApi = async (
  accessToken: string,
  projectId: string,
): Promise<{ id: string; deleted: boolean }> =>
  requestEnvelope<{ id: string; deleted: boolean }>(`/projects/${projectId}`, {
    method: 'DELETE',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const getProjectConversationsApi = async (
  accessToken: string,
  projectId: string,
): Promise<ConversationItem[]> =>
  requestEnvelope<{ conversations: ConversationItem[] }>(
    `/projects/${projectId}/conversations`,
    {
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
    },
  ).then((data) => data.conversations);

export const createConversationApi = async (
  accessToken: string,
  projectId: string,
  payload: { title?: string; selected_model?: string },
): Promise<ConversationItem> =>
  requestEnvelope<ConversationItem>(`/projects/${projectId}/conversations`, {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const getConversationApi = async (
  accessToken: string,
  conversationId: string,
): Promise<ConversationItem> =>
  requestEnvelope<ConversationItem>(`/conversations/${conversationId}`, {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const updateConversationApi = async (
  accessToken: string,
  conversationId: string,
  payload: { title?: string; selected_model?: string; status?: string },
): Promise<ConversationItem> =>
  requestEnvelope<ConversationItem>(`/conversations/${conversationId}`, {
    method: 'PUT',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const deleteConversationApi = async (
  accessToken: string,
  conversationId: string,
): Promise<{ id: string; deleted: boolean }> =>
  requestEnvelope<{ id: string; deleted: boolean }>(`/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const getConversationMessagesApi = async (
  accessToken: string,
  conversationId: string,
  cursor?: string | null,
): Promise<{ messages: MessageItem[]; next_cursor: string | null }> => {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
  return requestEnvelope<{ messages: MessageItem[]; next_cursor: string | null }>(
    `/conversations/${conversationId}/messages${query}`,
    {
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
    },
  );
};

export const createConversationMessageApi = async (
  accessToken: string,
  conversationId: string,
  payload: {
    content: string;
    selected_model?: string;
    source_url?: string;
    platforms?: string[];
    silent?: boolean;
  },
): Promise<ConversationMessageCreateResult> =>
  requestEnvelope<ConversationMessageCreateResult>(
    `/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
      body: JSON.stringify(payload),
    },
  );

type ChatStreamStatusEvent = { status: 'started' | 'processing' };
type ChatStreamDeltaEvent = { delta: string };
type ChatStreamErrorEvent = { error: string; code?: number };

type SseFrame = {
  event: string;
  data: string;
};

const parseJsonPayload = <T>(raw: string): T | null => {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
};

const parseSseFrame = (frameText: string): SseFrame | null => {
  const lines = frameText.split('\n');
  let eventName = 'message';
  const dataLines: string[] = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (!line || line.startsWith(':')) {
      continue;
    }

    const separatorIndex = line.indexOf(':');
    const field = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
    let value = separatorIndex === -1 ? '' : line.slice(separatorIndex + 1);
    if (value.startsWith(' ')) {
      value = value.slice(1);
    }

    if (field === 'event') {
      if (value) {
        eventName = value;
      }
      continue;
    }

    if (field === 'data') {
      dataLines.push(value);
    }
  }

  if (!dataLines.length) {
    return null;
  }

  return {
    event: eventName,
    data: dataLines.join('\n'),
  };
};

export const createConversationMessageStreamApi = async (
  accessToken: string,
  conversationId: string,
  payload: {
    content: string;
    selected_model?: string;
    source_url?: string;
    platforms?: string[];
    silent?: boolean;
  },
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
): Promise<ConversationMessageCreateResult> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/stream`, {
      method: 'POST',
      headers: {
        ...withAuthHeaders(accessToken),
        Accept: 'text/event-stream',
      },
      credentials: 'include',
      body: JSON.stringify(payload),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error;
    }
    throw new Error('Failed to fetch. Please check backend URL, CORS, and network connectivity.');
  }

  if (!response.ok) {
    let errorText = `Request failed with status ${response.status}.`;
    try {
      const failedPayload = (await response.json()) as { error?: unknown };
      if (failedPayload?.error) {
        errorText = String(failedPayload.error);
      }
    } catch {
      // ignore parser error and keep status-based fallback
    }
    throw new Error(errorText);
  }

  if (!response.body) {
    throw new Error('Streaming response body is missing.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let frameBuffer = '';
  let finalPayload: ConversationMessageCreateResult | null = null;

  const processFrameText = (frameText: string) => {
    const frame = parseSseFrame(frameText);
    if (!frame) {
      return;
    }

    if (frame.event === 'status') {
      parseJsonPayload<ChatStreamStatusEvent>(frame.data);
      return;
    }

    if (frame.event === 'delta') {
      const payloadData = parseJsonPayload<ChatStreamDeltaEvent>(frame.data);
      if (payloadData && typeof payloadData.delta === 'string') {
        onDelta(payloadData.delta);
      }
      return;
    }

    if (frame.event === 'error') {
      const payloadData = parseJsonPayload<ChatStreamErrorEvent>(frame.data);
      throw new Error(payloadData?.error || 'Streaming request failed.');
    }

    if (frame.event === 'done') {
      const payloadData = parseJsonPayload<ConversationMessageCreateResult>(frame.data);
      if (payloadData) {
        finalPayload = payloadData;
      }
    }
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    frameBuffer += decoder.decode(value, { stream: true });
    const normalizedBuffer = frameBuffer.replace(/\r\n/g, '\n');
    const frames = normalizedBuffer.split('\n\n');
    frameBuffer = frames.pop() ?? '';

    for (const frameText of frames) {
      processFrameText(frameText);
    }
  }

  frameBuffer += decoder.decode();
  if (frameBuffer.trim()) {
    processFrameText(frameBuffer.trim());
  }

  if (!finalPayload) {
    throw new Error('Streaming completed without final payload.');
  }
  return finalPayload;
};

export const getProjectHistoryApi = async (
  accessToken: string,
  projectId: string,
): Promise<RunItem[]> =>
  requestEnvelope<{ runs: RunItem[]; next_cursor: string | null }>(
    `/projects/${projectId}/history`,
    {
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
    },
  ).then((data) => data.runs);

export const getRunDetailApi = async (
  accessToken: string,
  runId: string,
): Promise<RunItem> =>
  requestEnvelope<RunItem>(`/runs/${runId}`, {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const saveRunSnapshotApi = async (
  accessToken: string,
  runId: string,
  payload: { content_plan_snapshot: Record<string, unknown> },
): Promise<{ id: string; saved: boolean }> =>
  requestEnvelope<{ id: string; saved: boolean }>(`/runs/${runId}/snapshot`, {
    method: 'PUT',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const restoreRunSnapshotApi = async (
  accessToken: string,
  runId: string,
  target: 'full_snapshot' | 'analysis' | 'linkedin' | 'facebook',
): Promise<{ restored_run: RunItem; content_plan_snapshot: Record<string, unknown> }> =>
  requestEnvelope<{ restored_run: RunItem; content_plan_snapshot: Record<string, unknown> }>(
    `/runs/${runId}/restore`,
    {
      method: 'POST',
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
      body: JSON.stringify({ target }),
    },
  );

export const createContentPlanApi = async (
  accessToken: string,
  payload: { url: string; additional_context?: string; selected_model?: string },
): Promise<ContentPlanData> =>
  requestEnvelope<ContentPlanData>('/content-plan', {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const publishSocialPostApi = async (
  accessToken: string,
  payload: { platform: SocialPublishPlatform; content: string; page_id?: string },
): Promise<SocialPublishResult> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/social/publish`, {
      method: 'POST',
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error('Failed to fetch. Please check backend URL, CORS, and network connectivity.');
  }

  let body: (ApiEnvelope<SocialPublishResult> & { code?: string | null }) | null = null;
  try {
    body = (await response.json()) as ApiEnvelope<SocialPublishResult> & { code?: string | null };
  } catch {
    // Keep null and rely on status-based fallback.
  }

  if (!response.ok || !body?.success || !body.data) {
    const err = new Error(body?.error || `Request failed with status ${response.status}.`) as Error & {
      code?: string;
      status?: number;
    };
    if (body?.code) {
      err.code = body.code;
    }
    err.status = response.status;
    throw err;
  }
  return body.data;
};

export const getFacebookPagesApi = async (
  accessToken: string,
): Promise<FacebookPageOption[]> =>
  requestEnvelope<FacebookPageOption[]>('/social/facebook/pages', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const createAutopostJobApi = async (
  accessToken: string,
  payload: {
    project_id: string;
    platform: AutopostPlatform;
    keyword: string;
    scheduled_at: string;
    publish_mode?: 'now' | 'schedule';
    page_id?: string;
  },
): Promise<{ id: string; status: string }> =>
  requestEnvelope<{ id: string; status: string }>('/autopost/jobs', {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const listAutopostJobsApi = async (
  accessToken: string,
  projectId: string,
  status?: string,
): Promise<AutopostJobItem[]> => {
  const params = new URLSearchParams({ project_id: projectId });
  if (status) params.set('status', status);
  return requestEnvelope<{ jobs: AutopostJobItem[] }>(
    `/autopost/jobs?${params.toString()}`,
    {
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
    },
  ).then((data) => data.jobs);
};

export const getAutopostCalendarApi = async (
  accessToken: string,
  projectId: string,
): Promise<AutopostJobItem[]> =>
  requestEnvelope<{ jobs: AutopostJobItem[] }>(
    `/autopost/calendar?project_id=${encodeURIComponent(projectId)}`,
    {
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
    },
  ).then((data) => data.jobs);

export const retryAutopostJobApi = async (
  accessToken: string,
  jobId: string,
): Promise<{ id: string; status: string }> =>
  requestEnvelope<{ id: string; status: string }>(`/autopost/jobs/${jobId}/retry`, {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const cancelAutopostJobApi = async (
  accessToken: string,
  jobId: string,
): Promise<{ id: string; status: string }> =>
  requestEnvelope<{ id: string; status: string }>(`/autopost/jobs/${jobId}/cancel`, {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });
