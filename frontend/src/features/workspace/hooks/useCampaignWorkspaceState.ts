import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ensureAuthenticatedAccessToken, meApi } from '@/features/auth/api/authApi';
import {
  createConversationApi,
  createConversationMessageApi,
  createConversationMessageStreamApi,
  getFacebookPagesApi,
  getConversationMessagesApi,
  getProjectByIdApi,
  getProjectHistoryApi,
  getProjectsApi,
  publishSocialPostApi,
  restoreRunSnapshotApi,
} from '../api/workspaceApi';
import { getActiveProjectId, setActiveProjectId } from '../projectStorage';
import {
  filterModelOptionsByVisibility,
  getProjectModelVisibility,
  MODEL_VISIBILITY_UPDATED_EVENT,
} from '../modelVisibilityStorage';
import type {
  CampaignResult,
  ContentPlanData,
  ContentSocialPost,
  ConversationMessageCreateResult,
  ConversationItem,
  FacebookPageOption,
  MessageItem,
  ProjectItem,
  RunItem,
  SocialPublishPlatform,
  SocialPublishResult,
  WorkspaceChatMessage,
} from '../types';
import type { UserItem } from '@/features/users/api/userApi';
import {
  extractContentPlanFromRun,
  parseContentPlanSnapshot,
} from '../historyUtils';

const DEFAULT_MODEL = 'gpt-4o-mini';
const INITIAL_ANALYSIS_PROMPT =
  'phan tich du an tu URL nay, chi cap nhat analysis, chua viet social post.';

export const REFINEMENT_SUGGESTIONS = [
  'Write a concise LinkedIn post from this analysis',
  'Write a friendly Facebook post from this analysis',
  'Rewrite LinkedIn in under 120 words',
  'Rewrite with a more professional tone',
];

export const MODEL_OPTIONS = [
  { value: 'gpt-5.4', label: 'GPT-5.4' },
  { value: 'gpt-5.1', label: 'GPT-5.1' },
  { value: 'gpt-5', label: 'GPT-5' },
  { value: 'gpt-4.1', label: 'GPT-4.1' },
  { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
  { value: 'gpt-4o', label: 'GPT-4o' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
  { value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
  { value: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' },
  { value: 'gemini-2.5-flash-lite', label: 'Gemini 2.5 Flash-Lite' },
  { value: 'gemini-3-pro-preview', label: 'Gemini 3 Pro (Preview)' },
  { value: 'gemini-3-flash-preview', label: 'Gemini 3 Flash (Preview)' },
];

const normalizeText = (value: string): string =>
  value.trim().replace(/\s+/g, ' ').toLowerCase();

const normalizePlatformPost = (post: ContentSocialPost): string => {
  const sections = [post.hook, post.body_content, post.call_to_action]
    .map((section) => section.trim())
    .filter(Boolean);
  if (post.hashtags.length) {
    sections.push(post.hashtags.join(' '));
  }
  return sections.join('\n\n');
};

const matchPlatform = (post: ContentSocialPost, aliases: string[]): boolean =>
  aliases.includes(post.platform.toLowerCase().trim());

const findPostText = (posts: ContentSocialPost[], aliases: string[]): string => {
  const post = posts.find((item) => matchPlatform(item, aliases));
  return post ? normalizePlatformPost(post) : '';
};

const findPost = (posts: ContentSocialPost[], aliases: string[]): ContentSocialPost | null =>
  posts.find((item) => matchPlatform(item, aliases)) ?? null;

const filterLegacyBootstrapMessages = (messages: MessageItem[]): MessageItem[] => {
  const filtered: MessageItem[] = [];
  const normalizedBootstrapPrompt = normalizeText(INITIAL_ANALYSIS_PROMPT);
  let firstUserHandled = false;
  let skipNextAssistant = false;

  for (const message of messages) {
    if (skipNextAssistant && message.role === 'assistant') {
      skipNextAssistant = false;
      continue;
    }

    if (
      message.role === 'user' &&
      !firstUserHandled &&
      normalizeText(message.content) === normalizedBootstrapPrompt
    ) {
      firstUserHandled = true;
      skipNextAssistant = true;
      continue;
    }

    if (message.role === 'user' && !firstUserHandled) {
      firstUserHandled = true;
    }

    filtered.push(message);
  }

  return filtered;
};

const extractContentPlanFromMessage = (
  messageResult: ConversationMessageCreateResult,
): ContentPlanData | null => {
  const directSnapshot = messageResult.content_plan_snapshot;
  if (directSnapshot) {
    const parsed = parseContentPlanSnapshot(directSnapshot);
    if (parsed) {
      return parsed;
    }
  }
  return extractContentPlanFromRun(messageResult.run);
};

const toCampaignResult = (
  contentPlan: ContentPlanData,
  run: RunItem | null,
  selectedModel: string,
): CampaignResult => {
  const posts = contentPlan.social_posts ?? [];
  return {
    analysis: contentPlan.analysis,
    linkedin: findPostText(posts, ['linkedin']),
    facebook: findPostText(posts, ['facebook']),
    twitter: findPostText(posts, ['twitter', 'x', 'twitter (x)']),
    posts: {
      linkedin: findPost(posts, ['linkedin']),
      facebook: findPost(posts, ['facebook']),
      twitter: findPost(posts, ['twitter', 'x', 'twitter (x)']),
    },
    meta: {
      source_url: contentPlan.source_url,
      run_id: run?.id ?? null,
      selected_model: selectedModel || null,
      updated_at: run?.finished_at || run?.createdAt || new Date().toISOString(),
    },
  };
};

const mapMessageRole = (role: string): WorkspaceChatMessage['role'] => {
  if (role === 'system' || role === 'assistant') {
    return role;
  }
  return 'user';
};

const toWorkspaceMessage = (message: MessageItem): WorkspaceChatMessage => ({
  id: message.id,
  role: mapMessageRole(message.role),
  content: message.content,
  createdAt: message.createdAt,
});

const findLatestRunWithSnapshot = (
  runs: RunItem[],
): { run: RunItem; contentPlan: ContentPlanData } | null => {
  for (const run of runs) {
    const contentPlan = extractContentPlanFromRun(run);
    if (contentPlan) {
      return { run, contentPlan };
    }
  }
  return null;
};

type WorkspaceState = {
  currentUser: UserItem | null;
  project: ProjectItem | null;
  conversation: ConversationItem | null;
  chatMessages: WorkspaceChatMessage[];
  campaignResult: CampaignResult | null;
  activeTab: number;
  prompt: string;
  selectedModel: string;
  modelOptions: { value: string; label: string }[];
  loadingWorkspace: boolean;
  loadingResult: boolean;
  refining: boolean;
  error: string | null;
  showSuggestionChips: boolean;
  historyRuns: RunItem[];
  historyLoading: boolean;
  historyError: string | null;
  restoringRunId: string | null;
  setPrompt: (value: string) => void;
  setSelectedModel: (value: string) => void;
  setActiveTab: (value: number) => void;
  sendRefinement: (suggestionPrompt?: string) => Promise<void>;
  cancelRefinement: () => void;
  refreshHistory: () => Promise<void>;
  restoreFromRun: (
    runId: string,
    target: 'full_snapshot' | 'analysis' | 'linkedin' | 'facebook' | 'twitter',
  ) => Promise<void>;
  publishSocialPost: (
    platform: SocialPublishPlatform,
    content: string,
    pageId?: string,
  ) => Promise<SocialPublishResult>;
  getFacebookPages: () => Promise<FacebookPageOption[]>;
  reload: () => Promise<void>;
};

export const useCampaignWorkspaceState = (): WorkspaceState => {
  const navigate = useNavigate();

  const [currentUser, setCurrentUser] = useState<UserItem | null>(null);
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [conversation, setConversation] = useState<ConversationItem | null>(null);
  const [conversationMessages, setConversationMessages] = useState<WorkspaceChatMessage[]>([]);
  const [campaignResult, setCampaignResult] = useState<CampaignResult | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [prompt, setPrompt] = useState('');
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [loadingWorkspace, setLoadingWorkspace] = useState(true);
  const [loadingResult, setLoadingResult] = useState(true);
  const [refining, setRefining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyRuns, setHistoryRuns] = useState<RunItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [restoringRunId, setRestoringRunId] = useState<string | null>(null);
  const [modelVisibilityRevision, setModelVisibilityRevision] = useState(0);
  const loadInFlightRef = useRef(false);
  const refinementAbortControllerRef = useRef<AbortController | null>(null);
  const refinementCancelRequestedRef = useRef(false);

  const modelOptions = useMemo(
    () =>
      project?.id
        ? filterModelOptionsByVisibility(
          MODEL_OPTIONS,
          getProjectModelVisibility(project.id),
        )
        : MODEL_OPTIONS,
    [project?.id, modelVisibilityRevision],
  );

  const waitForSnapshotRun = useCallback(
    async (
      accessToken: string,
      projectId: string,
    ): Promise<{ run: RunItem; contentPlan: ContentPlanData } | null> => {
      for (let attempt = 0; attempt < 4; attempt += 1) {
        const runs = await getProjectHistoryApi(accessToken, projectId);
        const snapshotCandidate = findLatestRunWithSnapshot(runs);
        if (snapshotCandidate) {
          return snapshotCandidate;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1200));
      }
      return null;
    },
    [],
  );

  const refreshHistory = useCallback(async (): Promise<void> => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken || !project?.id) {
      return;
    }
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const runs = await getProjectHistoryApi(accessToken, project.id);
      setHistoryRuns(runs);
    } catch (historyLoadError) {
      setHistoryError(
        historyLoadError instanceof Error ? historyLoadError.message : 'Failed to load history.',
      );
    } finally {
      setHistoryLoading(false);
    }
  }, [project?.id]);

  const loadWorkspace = useCallback(async (): Promise<void> => {
    if (loadInFlightRef.current) {
      return;
    }
    loadInFlightRef.current = true;
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) {
      loadInFlightRef.current = false;
      navigate({ to: '/login' });
      return;
    }

    setError(null);
    setLoadingWorkspace(true);
    setLoadingResult(true);
    try {
      const me = await meApi(accessToken);
      setCurrentUser(me);

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

      const ensuredConversation = await createConversationApi(accessToken, selectedProject.id, {
        title: `${selectedProject.name} Campaign`,
      });
      setConversation(ensuredConversation);
      const projectVisibleModels = filterModelOptionsByVisibility(
        MODEL_OPTIONS,
        getProjectModelVisibility(selectedProject.id),
      );
      const preferredModel = ensuredConversation.selected_model || DEFAULT_MODEL;
      const nextModel = projectVisibleModels.some((item) => item.value === preferredModel)
        ? preferredModel
        : projectVisibleModels[0]?.value || DEFAULT_MODEL;
      setSelectedModel(nextModel);

      const messagePayload = await getConversationMessagesApi(accessToken, ensuredConversation.id);
      setConversationMessages(
        filterLegacyBootstrapMessages(messagePayload.messages).map(toWorkspaceMessage),
      );

      const runs = await getProjectHistoryApi(accessToken, selectedProject.id);
      setHistoryRuns(runs);
      setHistoryError(null);
      const snapshotCandidate = findLatestRunWithSnapshot(runs);
      if (snapshotCandidate) {
        setCampaignResult(
          toCampaignResult(
            snapshotCandidate.contentPlan,
            snapshotCandidate.run,
            ensuredConversation.selected_model || DEFAULT_MODEL,
          ),
        );
        setLoadingResult(false);
        return;
      }

      if (!selectedProject.source_url) {
        setCampaignResult(null);
        setLoadingResult(false);
        return;
      }

      let bootstrapMessage: ConversationMessageCreateResult | null = null;
      try {
        bootstrapMessage = await createConversationMessageApi(
          accessToken,
          ensuredConversation.id,
          {
            content: INITIAL_ANALYSIS_PROMPT,
            selected_model: ensuredConversation.selected_model || DEFAULT_MODEL,
            source_url: selectedProject.source_url,
            silent: true,
          },
        );
      } catch (bootstrapError) {
        const bootstrapErrorText =
          bootstrapError instanceof Error ? bootstrapError.message : String(bootstrapError);
        if (!bootstrapErrorText.includes('An identical request is currently running')) {
          throw bootstrapError;
        }
      }

      const bootstrapSnapshot = bootstrapMessage
        ? extractContentPlanFromMessage(bootstrapMessage)
        : null;
      if (bootstrapSnapshot && bootstrapMessage) {
        setCampaignResult(
          toCampaignResult(
            bootstrapSnapshot,
            bootstrapMessage.run,
            ensuredConversation.selected_model || DEFAULT_MODEL,
          ),
        );
        return;
      }

      const delayedSnapshot = await waitForSnapshotRun(accessToken, selectedProject.id);
      if (delayedSnapshot) {
        setCampaignResult(
          toCampaignResult(
            delayedSnapshot.contentPlan,
            delayedSnapshot.run,
            ensuredConversation.selected_model || DEFAULT_MODEL,
          ),
        );
      } else {
        setCampaignResult(null);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load campaign workspace.');
    } finally {
      setLoadingWorkspace(false);
      setLoadingResult(false);
      loadInFlightRef.current = false;
    }
  }, [navigate, waitForSnapshotRun]);

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
    const onModelVisibilityUpdated = (event: Event) => {
      const customEvent = event as CustomEvent<{ projectId?: string }>;
      const updatedProjectId = customEvent.detail?.projectId;
      if (!project?.id || !updatedProjectId || updatedProjectId !== project.id) {
        return;
      }
      setModelVisibilityRevision((prev) => prev + 1);
    };
    window.addEventListener(MODEL_VISIBILITY_UPDATED_EVENT, onModelVisibilityUpdated);
    return () => {
      window.removeEventListener(MODEL_VISIBILITY_UPDATED_EVENT, onModelVisibilityUpdated);
    };
  }, [project?.id]);

  useEffect(() => {
    if (!modelOptions.length) {
      return;
    }
    if (!modelOptions.some((item) => item.value === selectedModel)) {
      setSelectedModel(modelOptions[0].value);
    }
  }, [modelOptions, selectedModel]);

  const sendRefinement = useCallback(
    async (suggestionPrompt?: string): Promise<void> => {
      const refinementPrompt = (suggestionPrompt ?? prompt).trim();
      if (!refinementPrompt || refining) {
        return;
      }

      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }

      if (!project || !conversation) {
        setError('No active project or conversation found.');
        return;
      }

      const tempUserId = `local-user-${Date.now()}`;
      const tempAssistantId = `local-assistant-${Date.now()}`;
      const refinementAbortController = new AbortController();
      refinementAbortControllerRef.current = refinementAbortController;
      refinementCancelRequestedRef.current = false;
      let pendingAssistantId = tempAssistantId;
      let streamedAssistantText = '';
      let queuedDeltaText = '';
      let typingTimerId: number | null = null;

      const updatePendingAssistant = () => {
        setConversationMessages((prev) =>
          prev.map((message) =>
            message.id === pendingAssistantId
              ? {
                ...message,
                content: streamedAssistantText || loadingAssistant.content,
                isLoading: true,
                }
              : message,
          ),
        );
      };

      const stopTypingTimer = () => {
        if (typingTimerId !== null) {
          window.clearInterval(typingTimerId);
          typingTimerId = null;
        }
      };

      const startTypingTimer = () => {
        if (typingTimerId !== null) {
          return;
        }
        typingTimerId = window.setInterval(() => {
          if (!queuedDeltaText) {
            return;
          }
          const step = Math.min(4, queuedDeltaText.length);
          streamedAssistantText += queuedDeltaText.slice(0, step);
          queuedDeltaText = queuedDeltaText.slice(step);
          updatePendingAssistant();
          if (!queuedDeltaText) {
            stopTypingTimer();
          }
        }, 18);
      };

      const flushPendingTyping = async () => {
        if (!queuedDeltaText) {
          stopTypingTimer();
          return;
        }

        startTypingTimer();
        await new Promise<void>((resolve) => {
          const waitForDrain = () => {
            if (!queuedDeltaText) {
              resolve();
              return;
            }
            window.setTimeout(waitForDrain, 20);
          };
          waitForDrain();
        });
      };

      const loadingAssistant: WorkspaceChatMessage = {
        id: tempAssistantId,
        role: 'assistant',
        content: '',
        isLoading: true,
        createdAt: new Date().toISOString(),
      };

      setError(null);
      setRefining(true);
      setPrompt('');
      setConversationMessages((prev) => [
        ...prev,
        {
          id: tempUserId,
          role: 'user',
          content: refinementPrompt,
          createdAt: new Date().toISOString(),
        },
        loadingAssistant,
      ]);

      try {
        const created = await createConversationMessageStreamApi(
          accessToken,
          conversation.id,
          {
            content: refinementPrompt,
            selected_model: selectedModel,
            source_url: project.source_url || undefined,
          },
          (delta) => {
            queuedDeltaText += delta;
            startTypingTimer();
          },
          refinementAbortController.signal,
        );
        await flushPendingTyping();
        if (!created.user_message || !created.assistant_message) {
          throw new Error('Unexpected silent response for interactive refinement.');
        }
        const userMessage = created.user_message;
        const assistantMessage = created.assistant_message;

        setConversationMessages((prev) =>
          prev.map((message) => {
            if (message.id === tempUserId) {
              return toWorkspaceMessage(userMessage);
            }
            if (message.id === tempAssistantId) {
              pendingAssistantId = assistantMessage.id;
              return {
                ...toWorkspaceMessage(assistantMessage),
                content: streamedAssistantText || loadingAssistant.content,
                isLoading: true,
              };
            }
            return message;
          }),
        );

        const updatedSnapshot = extractContentPlanFromMessage(created);
        if (updatedSnapshot) {
          setCampaignResult(toCampaignResult(updatedSnapshot, created.run, selectedModel));
          setActiveTab(0);
        }
        setHistoryRuns((prev) => [created.run, ...prev.filter((run) => run.id !== created.run.id)]);

        setConversationMessages((prev) =>
          prev.map((message) =>
            message.id === assistantMessage.id
              ? {
                ...message,
                isLoading: false,
                content: streamedAssistantText || assistantMessage.content,
                }
              : message,
          ),
        );
      } catch (refineError) {
        stopTypingTimer();
        const isCancelled =
          refineError instanceof DOMException && refineError.name === 'AbortError';

        if (isCancelled || refinementCancelRequestedRef.current) {
          await flushPendingTyping();
          setPrompt(refinementPrompt);
          setError(null);
          setConversationMessages((prev) =>
            prev.map((message) =>
              message.id === pendingAssistantId
                ? {
                  ...message,
                  role: 'system',
                  isLoading: false,
                  content: 'Bạn đã hủy câu hỏi này.',
                  }
                : message,
            ),
          );
          return;
        }

        setError(refineError instanceof Error ? refineError.message : 'Failed to refine campaign output.');
        setConversationMessages((prev) =>
          prev.map((message) =>
            message.id === pendingAssistantId
              ? {
                ...message,
                isLoading: false,
                content: 'I could not process this request right now. Please try again.',
                }
              : message,
          ),
        );
      } finally {
        stopTypingTimer();
        if (refinementAbortControllerRef.current === refinementAbortController) {
          refinementAbortControllerRef.current = null;
        }
        refinementCancelRequestedRef.current = false;
        setRefining(false);
      }
    },
    [conversation, navigate, project, prompt, refining, selectedModel],
  );

  const cancelRefinement = useCallback(() => {
    if (!refining) {
      return;
    }
    refinementCancelRequestedRef.current = true;
    refinementAbortControllerRef.current?.abort();
  }, [refining]);

  const restoreFromRun = useCallback(
    async (
      runId: string,
      target: 'full_snapshot' | 'analysis' | 'linkedin' | 'facebook' | 'twitter',
    ): Promise<void> => {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }
      if (!project) {
        setError('No active project found.');
        return;
      }

      setError(null);
      setHistoryError(null);
      setRestoringRunId(runId);
      try {
        const restored = await restoreRunSnapshotApi(accessToken, runId, target);
        const restoredSnapshot = parseContentPlanSnapshot(restored.content_plan_snapshot);
        if (!restoredSnapshot) {
          throw new Error('Restored run has invalid snapshot payload.');
        }

        const restoredModel = String(
          restored.restored_run.request_payload?.selected_model || selectedModel || DEFAULT_MODEL,
        );
        setCampaignResult(toCampaignResult(restoredSnapshot, restored.restored_run, restoredModel));
        setActiveTab(0);

        setConversationMessages((prev) => [
          ...prev,
          {
            id: `system-restore-${Date.now()}`,
            role: 'system',
            content: `Restored ${target} from version ${runId.slice(0, 8)}.`,
            createdAt: new Date().toISOString(),
          },
        ]);
        await refreshHistory();
      } catch (restoreError) {
        const rawMessage =
          restoreError instanceof Error ? restoreError.message : 'Failed to restore history run.';
        const message = rawMessage.includes('404')
          ? 'Restore endpoint not found. Please restart backend so /api/v1/runs/{run_id}/restore is loaded.'
          : rawMessage;
        setError(message);
        setHistoryError(message);
      } finally {
        setRestoringRunId(null);
      }
    },
    [navigate, project, refreshHistory, selectedModel],
  );

  const publishSocialPost = useCallback(
    async (
      platform: SocialPublishPlatform,
      content: string,
      pageId?: string,
    ): Promise<SocialPublishResult> => {
      const normalizedContent = content.trim();
      if (!normalizedContent) {
        throw new Error('No content to publish.');
      }
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        throw new Error('Unauthorized.');
      }
      return publishSocialPostApi(accessToken, {
        platform,
        content: normalizedContent,
        page_id: pageId?.trim() || undefined,
      });
    },
    [navigate],
  );

  const getFacebookPages = useCallback(async (): Promise<FacebookPageOption[]> => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) {
      navigate({ to: '/login' });
      throw new Error('Unauthorized.');
    }
    return getFacebookPagesApi(accessToken);
  }, [navigate]);

  const chatMessages = useMemo<WorkspaceChatMessage[]>(
    () => conversationMessages,
    [conversationMessages],
  );

  const showSuggestionChips = useMemo(
    () => conversationMessages.length === 0,
    [conversationMessages],
  );

  return {
    currentUser,
    project,
    conversation,
    chatMessages,
    campaignResult,
    activeTab,
    prompt,
    selectedModel,
    modelOptions,
    loadingWorkspace,
    loadingResult,
    refining,
    error,
    showSuggestionChips,
    historyRuns,
    historyLoading,
    historyError,
    restoringRunId,
    setPrompt,
    setSelectedModel,
    setActiveTab,
    sendRefinement,
    cancelRefinement,
    refreshHistory,
    restoreFromRun,
    publishSocialPost,
    getFacebookPages,
    reload: loadWorkspace,
  };
};
