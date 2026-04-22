import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Backdrop,
  Alert,
  Box,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { ArrowRight, FileText, Globe2, Plus, Sparkles, Trash2 } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { ensureAuthenticatedAccessToken } from '@/features/auth/api/authApi';
import brandLogo from '@/assets/app-logos/brand-logo.png';
import type { ProjectItem, RunItem } from '@/features/workspace/types';
import {
  getActiveProjectId,
  ONBOARDING_DONE_KEY,
  notifyProjectUpdated,
  setActiveProjectId,
} from '../projectStorage';
import {
  createConversationApi,
  createConversationMessageApi,
  createProjectApi,
  deleteProjectApi,
  getProjectHistoryApi,
  getProjectsApi,
} from '../api/workspaceApi';

const getProjectStatusMeta = (
  status: string | null,
): { label: string; color: string; background: string } => {
  const normalized = (status || '').toLowerCase();
  if (normalized === 'active') {
    return { label: 'Active', color: '#1f7a41', background: '#d8f5df' };
  }
  if (normalized === 'draft') {
    return { label: 'Draft', color: '#8a5a12', background: '#fbe5c8' };
  }
  if (normalized === 'archived') {
    return { label: 'Archived', color: '#5b6473', background: '#e8edf5' };
  }
  return { label: status || 'Unknown', color: '#5b6473', background: '#e8edf5' };
};

const INITIAL_ANALYSIS_PROMPT =
  'phan tich du an tu URL nay, chi cap nhat analysis, chua viet social post.';

const DEFAULT_MODEL = 'gpt-4o-mini';

const hasSnapshotPayload = (run: RunItem): boolean => {
  if (run.response_payload?.content_plan_snapshot) {
    return true;
  }
  const payload = run.response_payload;
  return Boolean(payload && payload.analysis && Array.isArray(payload.social_posts));
};

const WelcomeFeature: React.FC = () => {
  const navigate = useNavigate();
  const [projectNameInput, setProjectNameInput] = useState('');
  const [projectUrlInput, setProjectUrlInput] = useState('');
  const [existingProjects, setExistingProjects] = useState<ProjectItem[]>([]);
  const [selectedExistingProjectId, setSelectedExistingProjectId] = useState<string | null>(null);
  const [creatingNewProject, setCreatingNewProject] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loading, setLoading] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [pendingDeleteProject, setPendingDeleteProject] = useState<ProjectItem | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapOverlayOpen, setBootstrapOverlayOpen] = useState(false);
  const [bootstrapStep, setBootstrapStep] = useState<'preparing' | 'analyzing' | 'finalizing'>(
    'preparing',
  );
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);
  const [bootstrapProject, setBootstrapProject] = useState<ProjectItem | null>(null);

  const hasExistingProjects = existingProjects.length > 0;
  const shouldShowCreateForm = !hasExistingProjects || creatingNewProject;

  const isWelcomeValid = useMemo(
    () => projectNameInput.trim().length > 0 && projectUrlInput.trim().length > 0,
    [projectNameInput, projectUrlInput],
  );

  const loadExistingProjects = useCallback(async () => {
    setError(null);
    setLoadingProjects(true);
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) {
      navigate({ to: '/login' });
      return;
    }

    try {
      const projects = await getProjectsApi(accessToken);
      setExistingProjects(projects);
      if (projects.length > 0) {
        const currentProjectId = getActiveProjectId();
        const selected =
          projects.find((project) => project.id === currentProjectId) || projects[0];
        setSelectedExistingProjectId(selected.id);
      } else {
        setSelectedExistingProjectId(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects.');
    } finally {
      setLoadingProjects(false);
    }
  }, [navigate]);

  useEffect(() => {
    void loadExistingProjects();
  }, [loadExistingProjects]);

  const waitForBootstrapSnapshot = useCallback(
    async (accessToken: string, projectId: string): Promise<boolean> => {
      for (let attempt = 0; attempt < 12; attempt += 1) {
        const runs = await getProjectHistoryApi(accessToken, projectId);
        if (runs.some(hasSnapshotPayload)) {
          return true;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1200));
      }
      return false;
    },
    [],
  );

  const bootstrapProjectAnalysis = useCallback(
    async (project: ProjectItem): Promise<boolean> => {
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return false;
      }

      setBootstrapProject(project);
      setBootstrapOverlayOpen(true);
      setBootstrapError(null);
      setBootstrapStep('preparing');
      try {
        const conversation = await createConversationApi(accessToken, project.id, {
          title: `${project.name} Campaign`,
        });

        setBootstrapStep('analyzing');
        try {
          await createConversationMessageApi(accessToken, conversation.id, {
            content: INITIAL_ANALYSIS_PROMPT,
            selected_model: conversation.selected_model || DEFAULT_MODEL,
            source_url: project.source_url || undefined,
            silent: true,
          });
        } catch (analysisError) {
          const message =
            analysisError instanceof Error ? analysisError.message : String(analysisError);
          if (!message.includes('An identical request is currently running')) {
            throw analysisError;
          }
        }

        const ready = await waitForBootstrapSnapshot(accessToken, project.id);
        if (!ready) {
          throw new Error(
            'Analysis is taking longer than expected. Please retry to continue.',
          );
        }

        setBootstrapStep('finalizing');
        await new Promise((resolve) => window.setTimeout(resolve, 350));
        setActiveProjectId(project.id);
        localStorage.setItem(ONBOARDING_DONE_KEY, 'true');
        notifyProjectUpdated();
        navigate({ to: '/workspace' });
        return true;
      } catch (err) {
        setBootstrapError(
          err instanceof Error ? err.message : 'Failed to analyze project.',
        );
        return false;
      }
    },
    [navigate, waitForBootstrapSnapshot],
  );

  const handleUseExistingProject = () => {
    if (!selectedExistingProjectId) return;
    setActiveProjectId(selectedExistingProjectId);
    localStorage.setItem(ONBOARDING_DONE_KEY, 'true');
    notifyProjectUpdated();
    navigate({ to: '/workspace' });
  };

  const confirmDeleteProject = useCallback(
    async (project: ProjectItem) => {
      if (deletingProjectId) return;
      const accessToken = await ensureAuthenticatedAccessToken();
      if (!accessToken) {
        navigate({ to: '/login' });
        return;
      }

      try {
        setError(null);
        setDeletingProjectId(project.id);
        await deleteProjectApi(accessToken, project.id);
        setExistingProjects((prev) => {
          const next = prev.filter((item) => item.id !== project.id);
          setSelectedExistingProjectId((selected) => {
            if (selected !== project.id) return selected;
            return next[0]?.id ?? null;
          });
          if (next.length === 0) {
            setCreatingNewProject(true);
          }
          return next;
        });
        notifyProjectUpdated();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete project.');
      } finally {
        setDeletingProjectId(null);
        setPendingDeleteProject(null);
      }
    },
    [deletingProjectId, navigate],
  );

  const handleContinue = async () => {
    if (hasExistingProjects && !creatingNewProject) {
      handleUseExistingProject();
      return;
    }

    if (!isWelcomeValid) return;
    setError(null);
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) {
      navigate({ to: '/login' });
      return;
    }

    setLoading(true);
    try {
      const project = await createProjectApi(accessToken, {
        name: projectNameInput.trim(),
        source_url: projectUrlInput.trim(),
      });
      const success = await bootstrapProjectAnalysis(project);
      if (!success) {
        await loadExistingProjects();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        height: '100vh',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        px: { xs: 1.2, md: 2.4 },
        py: { xs: 1, md: 1.6 },
        overflow: 'hidden',
        background:
          'radial-gradient(120% 90% at 50% 0%, #eff7ff 0%, #d7e8f8 55%, #c8def3 100%)',
      }}
    >
      <Paper
        elevation={0}
        sx={{
          width: '100%',
          maxWidth: 1220,
          maxHeight: 'calc(100vh - 22px)',
          borderRadius: 2,
          overflow: 'hidden',
          border: '1px solid #d6dfeb',
          boxShadow: '0 28px 60px rgba(35, 67, 99, 0.24)',
          bgcolor: '#ffffff',
        }}
      >
        <Box
          sx={{
            height: 66,
            px: { xs: 2, md: 2.5 },
            borderBottom: '1px solid #e2e8f0',
            bgcolor: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-start',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.1 }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Box
                component="img"
                src={brandLogo}
                alt="AI Content Planner logo"
                sx={{ width: 26, height: 26, objectFit: 'contain' }}
              />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: { xs: '1.1rem', md: '2rem' }, color: '#0f172a' }}>
              AI Content Planner
            </Typography>
          </Box>
        </Box>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', lg: '1.1fr 1fr' },
            minHeight: { xs: 'auto', lg: 620 },
          }}
        >
          <Box
            sx={{
              px: { xs: 2.2, md: 4 },
              py: { xs: 2.2, md: 3.2 },
              bgcolor: '#ffffff',
              borderRight: { xs: 'none', lg: '1px solid #e6eaf0' },
            }}
          >
            <Typography
              sx={{
                fontSize: { xs: '2.05rem', md: '3.3rem' },
                lineHeight: 1.08,
                fontWeight: 800,
                letterSpacing: '-0.03em',
                color: '#1e293b',
                maxWidth: 780,
              }}
            >
              {shouldShowCreateForm ? 'Welcome. Let’s optimize your website together.' : 'Select your project'}
            </Typography>

            <Typography sx={{ mt: 1.8, color: '#4f5f74', maxWidth: 720, fontSize: { xs: '1rem', md: '1.08rem' } }}>
              {shouldShowCreateForm
                ? 'We will use your website to improve AI search visibility, strengthen SEO, and generate relevant content ideas.'
                : 'We found projects in your account. Pick one to continue in workspace.'}
            </Typography>

            {loadingProjects ? (
              <Box sx={{ mt: 4, display: 'flex', alignItems: 'center', gap: 1.2 }}>
                <CircularProgress size={20} />
                <Typography color="text.secondary">Loading projects...</Typography>
              </Box>
            ) : !shouldShowCreateForm ? (
              <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 1.2 }}>
                {existingProjects.map((project) => {
                  const selected = selectedExistingProjectId === project.id;
                  const statusMeta = getProjectStatusMeta(project.status || null);
                  return (
                    <Paper
                      key={project.id}
                      variant="outlined"
                      onClick={() => setSelectedExistingProjectId(project.id)}
                      sx={{
                        p: 1.35,
                        pr: 6.2,
                        position: 'relative',
                        borderRadius: 2,
                        cursor: 'pointer',
                        borderColor: selected ? '#2f8cab' : '#cfd8e3',
                        borderWidth: selected ? 2 : 1,
                        bgcolor: selected ? '#eef7fb' : '#f8fafc',
                        boxShadow: selected ? '0 0 0 3px rgba(47, 140, 171, 0.12)' : 'none',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <Tooltip title="Delete project">
                        <span>
                          <IconButton
                            size="small"
                            aria-label={`Delete project ${project.name}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              setPendingDeleteProject(project);
                            }}
                            disabled={Boolean(deletingProjectId)}
                            sx={{
                              position: 'absolute',
                              top: 8,
                              right: 8,
                              border: '1px solid',
                              borderColor: '#d6dde8',
                              bgcolor: '#ffffff',
                              color: '#8b97a8',
                              '&:hover': {
                                bgcolor: '#fee2e2',
                                color: '#b91c1c',
                                borderColor: '#fecaca',
                              },
                            }}
                          >
                            {deletingProjectId === project.id ? (
                              <CircularProgress size={14} />
                            ) : (
                              <Trash2 size={14} />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.4 }}>
                        <Box
                          sx={{
                            width: 50,
                            height: 50,
                            borderRadius: 1.8,
                            bgcolor: '#d7e7f8',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#1e3a5f',
                            flexShrink: 0,
                          }}
                        >
                          {statusMeta.label === 'Active' ? (
                            <Box
                              component="img"
                              src={brandLogo}
                              alt="AI Content Planner logo"
                              sx={{ width: 24, height: 24, objectFit: 'contain' }}
                            />
                          ) : (
                            <FileText size={22} />
                          )}
                        </Box>

                        <Box sx={{ flex: 1, minWidth: 0 }}>
                          <Typography sx={{ fontWeight: 800, color: '#111827', fontSize: '1.45rem', lineHeight: 1.2 }}>
                            {project.name}
                          </Typography>
                          <Typography
                            sx={{
                              mt: 0.6,
                              color: '#3e556f',
                              fontSize: '1.12rem',
                              lineHeight: 1.4,
                              wordBreak: 'break-word',
                            }}
                          >
                            {project.source_url || 'No URL'}
                          </Typography>
                        </Box>
                      </Box>
                    </Paper>
                  );
                })}

                <Button
                  variant="outlined"
                  startIcon={<Plus size={17} />}
                  onClick={() => {
                    setCreatingNewProject(true);
                    setError(null);
                  }}
                  sx={{
                    mt: 1,
                    alignSelf: 'flex-start',
                    textTransform: 'none',
                    fontWeight: 700,
                    borderRadius: 999,
                    px: 2.2,
                    py: 1,
                    borderColor: '#c5d2e2',
                    color: '#111827',
                    bgcolor: '#ffffff',
                  }}
                >
                  Create new project
                </Button>
              </Box>
            ) : (
              <Box sx={{ mt: 4, maxWidth: 760 }}>
                <TextField
                  label="Website URL"
                  placeholder="https://example.com"
                  value={projectUrlInput}
                  onChange={(event) => setProjectUrlInput(event.target.value)}
                  fullWidth
                  size="medium"
                  InputProps={{
                    startAdornment: (
                      <Box sx={{ display: 'flex', alignItems: 'center', mr: 1, color: '#557289' }}>
                        <Globe2 size={16} />
                      </Box>
                    ),
                  }}
                />

                <TextField
                  label="Project name"
                  placeholder="Enter project name"
                  value={projectNameInput}
                  onChange={(event) => setProjectNameInput(event.target.value)}
                  fullWidth
                  sx={{ mt: 2 }}
                />

                {hasExistingProjects && (
                  <Button
                    variant="text"
                    onClick={() => {
                      setCreatingNewProject(false);
                      setError(null);
                    }}
                    sx={{ mt: 1.1, px: 0, textTransform: 'none', fontWeight: 700 }}
                  >
                    Back to existing projects
                  </Button>
                )}
              </Box>
            )}

            {error && (
              <Alert severity="error" sx={{ mt: 2, maxWidth: 760 }}>
                {error}
              </Alert>
            )}
          </Box>

          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              px: { xs: 2.2, md: 3.4 },
              py: { xs: 2.2, md: 2.8 },
              background:
                'linear-gradient(145deg, #8ea4f4 0%, #8d9ef2 36%, #a8b5f9 100%)',
            }}
          >
            <Paper
              elevation={0}
              sx={{
                borderRadius: 3,
                border: '1px solid rgba(255,255,255,0.45)',
                bgcolor: 'rgba(241, 246, 255, 0.3)',
                backdropFilter: 'blur(2px)',
                px: { xs: 1.4, md: 2.2 },
                py: { xs: 1.4, md: 2.1 },
                minHeight: { xs: 280, md: 420 },
              }}
            >
              <Box sx={{ display: 'flex', gap: 1.1, alignItems: 'flex-start', mb: 2 }}>
                <Box
                  sx={{
                    width: 34,
                    height: 34,
                    borderRadius: '50%',
                    bgcolor: '#c6e8ff',
                    color: '#1f4d78',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Sparkles size={15} />
                </Box>
                <Paper
                  elevation={0}
                  sx={{
                    px: 2,
                    py: 1.15,
                    borderRadius: 2.4,
                    border: 'none',
                    bgcolor: 'rgba(255,255,255,0.88)',
                  }}
                >
                  <Typography sx={{ color: '#1f2937', fontSize: '1.1rem' }}>
                    <strong>AI:</strong> How can I help with your content today?
                  </Typography>
                </Paper>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
                <Paper
                  elevation={0}
                  sx={{
                    maxWidth: '80%',
                    px: 2,
                    py: 1.15,
                    borderRadius: 2.4,
                    border: 'none',
                    bgcolor: 'rgba(219, 233, 255, 0.88)',
                  }}
                >
                  <Typography sx={{ color: '#1f2937', fontSize: '1.1rem' }}>
                    <strong>User:</strong> Draft an intro for the new LLM project.
                  </Typography>
                </Paper>
              </Box>

              <Box sx={{ display: 'flex', gap: 1.1, alignItems: 'flex-start' }}>
                <Box
                  sx={{
                    width: 34,
                    height: 34,
                    borderRadius: '50%',
                    bgcolor: '#c6e8ff',
                    color: '#1f4d78',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}
                >
                  <Sparkles size={15} />
                </Box>
                <Paper
                  elevation={0}
                  sx={{
                    flex: 1,
                    px: 2,
                    py: 1.15,
                    borderRadius: 2.4,
                    border: 'none',
                    bgcolor: 'rgba(255,255,255,0.88)',
                  }}
                >
                  <Typography sx={{ color: '#1f2937', fontSize: '1.1rem', mb: 1 }}>
                    <strong>AI:</strong> Sure! Here&apos;s a draft...
                  </Typography>
                  {[76, 68, 82, 62].map((width, index) => (
                    <Box
                      key={width + index}
                      sx={{
                        height: 12,
                        borderRadius: 999,
                        mt: index === 0 ? 0 : 1,
                        width: `${width}%`,
                        bgcolor: '#d3dced',
                      }}
                    />
                  ))}
                </Paper>
              </Box>
            </Paper>

            <Button
              variant="contained"
              endIcon={<ArrowRight size={18} />}
              onClick={handleContinue}
              disabled={
                loadingProjects ||
                loading ||
                (hasExistingProjects && !creatingNewProject
                  ? !selectedExistingProjectId
                  : !isWelcomeValid)
              }
              sx={{
                mt: 2.6,
                width: '100%',
                borderRadius: 999,
                py: 1.4,
                fontWeight: 800,
                fontSize: '1.4rem',
                boxShadow: '0 10px 30px rgba(12, 70, 146, 0.35)',
              }}
            >
              {loading
                ? 'Processing...'
                : hasExistingProjects && !creatingNewProject
                  ? 'Continue with selected project'
                  : 'Continue'}
            </Button>
          </Box>
        </Box>
      </Paper>

      <Backdrop
        open={bootstrapOverlayOpen}
        sx={{
          zIndex: (theme) => theme.zIndex.modal + 10,
          bgcolor: 'rgba(11, 18, 31, 0.46)',
          backdropFilter: 'blur(3px)',
        }}
      >
        <Paper
          elevation={0}
          sx={{
            width: 'min(560px, calc(100vw - 28px))',
            borderRadius: 2.4,
            p: { xs: 2, md: 2.4 },
            border: '1px solid #d7e0ed',
            boxShadow: '0 18px 50px rgba(15, 23, 42, 0.35)',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.1, mb: 1.6 }}>
            <CircularProgress size={18} />
            <Typography sx={{ fontWeight: 800, color: '#0f172a', fontSize: '1.05rem' }}>
              Preparing your campaign workspace...
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.9 }}>
            {[
              { key: 'preparing', label: 'Preparing campaign' },
              { key: 'analyzing', label: 'Analyzing source URL' },
              { key: 'finalizing', label: 'Finalizing workspace' },
            ].map((item, index) => {
              const activeIndex =
                bootstrapStep === 'preparing'
                  ? 0
                  : bootstrapStep === 'analyzing'
                    ? 1
                    : 2;
              const isDone = index < activeIndex;
              const isActive = index === activeIndex;
              return (
                <Box
                  key={item.key}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    py: 0.55,
                    color: isDone || isActive ? '#0f172a' : '#64748b',
                  }}
                >
                  <Box
                    sx={{
                      width: 18,
                      height: 18,
                      borderRadius: '50%',
                      border: '1px solid',
                      borderColor: isDone || isActive ? '#2563eb' : '#cbd5e1',
                      bgcolor: isDone ? '#2563eb' : '#ffffff',
                    }}
                  />
                  <Typography sx={{ fontSize: '0.96rem', fontWeight: isActive ? 700 : 600 }}>
                    {item.label}
                  </Typography>
                </Box>
              );
            })}
          </Box>

          {bootstrapError && (
            <Alert severity="error" sx={{ mt: 1.6 }}>
              {bootstrapError}
            </Alert>
          )}

          {bootstrapError && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1, mt: 1.4 }}>
              <Button
                onClick={() => setBootstrapOverlayOpen(false)}
                variant="text"
              >
                Close
              </Button>
              <Button
                variant="contained"
                onClick={() => {
                  if (bootstrapProject) {
                    void bootstrapProjectAnalysis(bootstrapProject);
                  }
                }}
              >
                Retry analysis
              </Button>
            </Box>
          )}
        </Paper>
      </Backdrop>

      <Dialog
        open={pendingDeleteProject !== null}
        onClose={() => {
          if (!deletingProjectId) {
            setPendingDeleteProject(null);
          }
        }}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700 }}>Delete project?</DialogTitle>
        <DialogContent>
          <Typography color="text.secondary" sx={{ mt: 0.5 }}>
            {pendingDeleteProject
              ? `Project "${pendingDeleteProject.name}" will be permanently deleted.`
              : ''}
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.2 }}>
          <Button
            onClick={() => setPendingDeleteProject(null)}
            disabled={Boolean(deletingProjectId)}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={!pendingDeleteProject || Boolean(deletingProjectId)}
            onClick={() => {
              if (pendingDeleteProject) {
                void confirmDeleteProject(pendingDeleteProject);
              }
            }}
            startIcon={deletingProjectId ? <CircularProgress size={14} color="inherit" /> : undefined}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default WelcomeFeature;
