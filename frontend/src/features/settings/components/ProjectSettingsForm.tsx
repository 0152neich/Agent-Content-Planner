import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Divider,
  FormControlLabel,
  Paper,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { Save } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { useSnackbar } from '~components/AppLayout';
import { ensureAuthenticatedAccessToken } from '@/features/auth/api/authApi';
import { getProjectByIdApi, updateProjectApi } from '@/features/workspace/api/workspaceApi';
import {
  buildDefaultModelVisibility,
  getProjectModelVisibility,
  setProjectModelVisibility,
  type ProjectModelVisibility,
} from '@/features/workspace/modelVisibilityStorage';
import { MODEL_OPTIONS } from '@/features/workspace/hooks/useCampaignWorkspaceState';
import { getActiveProjectId, notifyProjectUpdated } from '@/features/workspace/projectStorage';
import type { ProjectItem } from '@/features/workspace/types';

type ProjectSettingsFormProps = {
  embedded?: boolean;
  hideHeader?: boolean;
  onSaved?: () => void;
};

const MODEL_GROUPS = [
  {
    key: 'openai',
    label: 'OpenAI (GPT)',
    match: (value: string) => value.startsWith('gpt-'),
  },
  {
    key: 'anthropic',
    label: 'Anthropic (Claude)',
    match: (value: string) => value.startsWith('claude-'),
  },
  {
    key: 'gemini',
    label: 'Google (Gemini)',
    match: (value: string) => value.startsWith('gemini-'),
  },
] as const;

const countEnabled = (visibility: ProjectModelVisibility): number =>
  Object.values(visibility).filter(Boolean).length;

export const ProjectSettingsForm: React.FC<ProjectSettingsFormProps> = ({
  embedded = false,
  hideHeader = false,
  onSaved,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { showSnackbar } = useSnackbar();
  const [project, setProject] = useState<ProjectItem | null>(null);
  const [projectName, setProjectName] = useState('');
  const [modelVisibility, setModelVisibilityState] = useState<ProjectModelVisibility>(
    buildDefaultModelVisibility(MODEL_OPTIONS),
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const groupedModelOptions = useMemo(
    () =>
      MODEL_GROUPS.map((group) => ({
        key: group.key,
        label: group.label,
        models: MODEL_OPTIONS.filter((model) => group.match(model.value)),
      })),
    [],
  );

  const loadProjectSettings = useCallback(async () => {
    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }

    const activeProjectId = getActiveProjectId();
    if (!activeProjectId) {
      setError(t('settingsProject.errors.noActiveProject'));
      setLoading(false);
      return;
    }

    try {
      setError(null);
      setLoading(true);
      const fetchedProject = await getProjectByIdApi(token, activeProjectId);
      setProject(fetchedProject);
      setProjectName(fetchedProject.name || '');
      setModelVisibilityState(
        getProjectModelVisibility(activeProjectId) ??
        buildDefaultModelVisibility(MODEL_OPTIONS),
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t('settingsProject.errors.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    void loadProjectSettings();
  }, [loadProjectSettings]);

  useEffect(() => {
    const refresh = () => {
      void loadProjectSettings();
    };

    window.addEventListener('project-updated', refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener('project-updated', refresh);
      window.removeEventListener('storage', refresh);
    };
  }, [loadProjectSettings]);

  const enabledCount = useMemo(() => countEnabled(modelVisibility), [modelVisibility]);

  const toggleModelVisibility = (modelValue: string, nextEnabled: boolean) => {
    setError(null);
    setModelVisibilityState((prev) => {
      if (!nextEnabled && prev[modelValue] !== false && countEnabled(prev) <= 1) {
        setError(t('settingsProject.errors.atLeastOneModel'));
        return prev;
      }
      const next = { ...prev, [modelValue]: nextEnabled };
      if (project?.id) {
        setProjectModelVisibility(project.id, next);
      }
      return next;
    });
  };

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving || !project) return;

    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      navigate({ to: '/login' });
      return;
    }

    const normalizedName = projectName.trim();
    if (!normalizedName) {
      setError(t('settingsProject.errors.projectNameRequired'));
      return;
    }
    if (enabledCount < 1) {
      setError(t('settingsProject.errors.atLeastOneModel'));
      return;
    }

    try {
      setSaving(true);
      setError(null);

      if (normalizedName !== project.name) {
        const updated = await updateProjectApi(token, project.id, { name: normalizedName });
        setProject(updated);
        setProjectName(updated.name);
      }

      setProjectModelVisibility(project.id, modelVisibility);
      notifyProjectUpdated();
      showSnackbar(t('settingsProject.saved'), 'success');
      onSaved?.();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t('settingsProject.errors.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const content = (
    <>
      {!hideHeader && (
        <>
          <Box sx={{ mb: 1.8 }}>
            <Typography variant="h5" sx={{ fontWeight: 800, mb: 0.4 }}>
              {t('settingsProject.title')}
            </Typography>
            <Typography color="text.secondary">
              {t('settingsProject.subtitle')}
            </Typography>
          </Box>
          <Divider sx={{ mb: 2.4 }} />
        </>
      )}

      {loading ? (
        <Box sx={{ minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
          <CircularProgress size={18} />
          <Typography color="text.secondary">{t('settingsProject.loading')}</Typography>
        </Box>
      ) : (
        <Box component="form" onSubmit={handleSave}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Stack spacing={2}>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
                gap: 1.5,
              }}
            >
              <TextField
                label={t('settingsProject.fields.projectName')}
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                required
                fullWidth
              />
              <TextField
                label={t('settingsProject.fields.projectLink')}
                value={project?.source_url || ''}
                fullWidth
                InputProps={{ readOnly: true }}
              />
            </Box>

            <Box
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 2,
                px: 1.7,
                py: 1.5,
              }}
            >
              <Typography sx={{ fontWeight: 700, fontSize: '0.95rem' }}>
                {t('settingsProject.modelVisibility.title')}
              </Typography>
              <Typography color="text.secondary" sx={{ mt: 0.45, mb: 1.1, fontSize: '0.88rem' }}>
                {t('settingsProject.modelVisibility.subtitle')}
              </Typography>

              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', md: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(3, minmax(0, 1fr))' },
                  gap: 1.1,
                }}
              >
                {groupedModelOptions.map((group) => (
                  <Box
                    key={group.key}
                    sx={{
                      border: '1px solid',
                      borderColor: 'divider',
                      borderRadius: 1.5,
                      px: 1.2,
                      py: 1.05,
                    }}
                  >
                    <Typography sx={{ fontWeight: 700, fontSize: '0.84rem', mb: 0.6 }}>
                      {group.label}
                    </Typography>
                    <Stack spacing={0.2}>
                      {group.models.map((model) => {
                        const checked = modelVisibility[model.value] !== false;
                        return (
                          <FormControlLabel
                            key={model.value}
                            control={
                              <Switch
                                checked={checked}
                                onChange={(event) => toggleModelVisibility(model.value, event.target.checked)}
                                size="small"
                              />
                            }
                            label={model.label}
                            sx={{
                              m: 0,
                              py: 0.15,
                              '& .MuiFormControlLabel-label': { fontSize: '0.87rem' },
                            }}
                          />
                        );
                      })}
                    </Stack>
                  </Box>
                ))}
              </Box>

              <Typography color="text.secondary" sx={{ mt: 0.9, fontSize: '0.78rem' }}>
                {t('settingsProject.modelVisibility.enabledCount', { enabled: enabledCount, total: MODEL_OPTIONS.length })}
              </Typography>
            </Box>
          </Stack>

          <Box sx={{ mt: 2.3, display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              type="submit"
              variant="contained"
              disabled={saving}
              startIcon={saving ? <CircularProgress size={14} color="inherit" /> : <Save size={16} />}
              sx={{ minWidth: 160, fontWeight: 700 }}
            >
              {saving ? t('settingsProject.saving') : t('settingsProject.saveButton')}
            </Button>
          </Box>
        </Box>
      )}
    </>
  );

  if (embedded) {
    return (
      <Box sx={{ width: '100%', bgcolor: 'background.paper', p: { xs: 1.2, md: 1.8 } }}>
        {content}
      </Box>
    );
  }

  return (
    <Paper
      sx={{
        width: '100%',
        borderRadius: 3,
        border: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.paper',
        p: { xs: 2.5, md: 3.5 },
      }}
    >
      {content}
    </Paper>
  );
};

export const ProjectSettingsFeature: React.FC = () => (
  <ProjectSettingsForm />
);
