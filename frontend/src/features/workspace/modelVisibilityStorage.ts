import type { ProjectItem } from './types';

export type ProjectModelVisibility = Record<string, boolean>;

const KEY_PREFIX = 'workspace-model-visibility::';
export const MODEL_VISIBILITY_UPDATED_EVENT = 'project-model-visibility-updated';

const buildKey = (projectId: string) => `${KEY_PREFIX}${projectId}`;

export const getProjectModelVisibility = (
  projectId: string,
): ProjectModelVisibility | null => {
  try {
    const raw = localStorage.getItem(buildKey(projectId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return Object.fromEntries(
      Object.entries(parsed).map(([key, value]) => [key, Boolean(value)]),
    );
  } catch {
    return null;
  }
};

export const setProjectModelVisibility = (
  projectId: string,
  value: ProjectModelVisibility,
) => {
  localStorage.setItem(buildKey(projectId), JSON.stringify(value));
  window.dispatchEvent(
    new CustomEvent<{ projectId: string }>(MODEL_VISIBILITY_UPDATED_EVENT, {
      detail: { projectId },
    }),
  );
};

export const buildDefaultModelVisibility = (
  modelOptions: Array<{ value: string }>,
): ProjectModelVisibility =>
  Object.fromEntries(modelOptions.map((option) => [option.value, true]));

export const filterModelOptionsByVisibility = <T extends { value: string }>(
  modelOptions: T[],
  visibility: ProjectModelVisibility | null,
): T[] => {
  if (!visibility) return modelOptions;
  const filtered = modelOptions.filter((option) => visibility[option.value] !== false);
  return filtered.length > 0 ? filtered : [modelOptions[0]];
};

export const hydrateModelVisibilityForProject = (
  project: ProjectItem,
  modelOptions: Array<{ value: string }>,
): ProjectModelVisibility => {
  return (
    getProjectModelVisibility(project.id) ?? buildDefaultModelVisibility(modelOptions)
  );
};
