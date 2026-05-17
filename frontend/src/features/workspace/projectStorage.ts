export const ACTIVE_PROJECT_ID_KEY = 'workspace-active-project-id';
export const ONBOARDING_DONE_KEY = 'workspace-onboarding-done';

export const notifyProjectUpdated = () => {
  window.dispatchEvent(new Event('project-updated'));
};

export const setActiveProjectId = (projectId: string) => {
  localStorage.setItem(ACTIVE_PROJECT_ID_KEY, projectId);
  notifyProjectUpdated();
};

export const getActiveProjectId = (): string | null =>
  localStorage.getItem(ACTIVE_PROJECT_ID_KEY);
