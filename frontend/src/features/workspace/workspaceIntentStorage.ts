export type WorkspaceIntent = {
  source: 'autopost';
  target_platform: 'linkedin' | 'facebook';
  timestamp: string;
};

const WORKSPACE_INTENT_KEY = 'workspace_intent_v1';

export const setWorkspaceIntent = (intent: WorkspaceIntent): void => {
  try {
    localStorage.setItem(WORKSPACE_INTENT_KEY, JSON.stringify(intent));
  } catch {
    // no-op
  }
};

export const getWorkspaceIntent = (): WorkspaceIntent | null => {
  try {
    const raw = localStorage.getItem(WORKSPACE_INTENT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<WorkspaceIntent>;
    if (
      parsed.source !== 'autopost' ||
      (parsed.target_platform !== 'linkedin' && parsed.target_platform !== 'facebook')
    ) {
      return null;
    }
    return {
      source: 'autopost',
      target_platform: parsed.target_platform,
      timestamp: String(parsed.timestamp || new Date().toISOString()),
    };
  } catch {
    return null;
  }
};

export const clearWorkspaceIntent = (): void => {
  try {
    localStorage.removeItem(WORKSPACE_INTENT_KEY);
  } catch {
    // no-op
  }
};
