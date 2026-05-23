import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { ExternalLink, Eye } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { ensureAuthenticatedAccessToken } from '@/features/auth/api/authApi';
import {
  getProjectHistoryApi,
  getProjectsApi,
  getRunDetailApi,
} from '@/features/workspace/api/workspaceApi';
import { getRunLastUpdatedAt } from '@/features/workspace/historyUtils';
import {
  getActiveProjectId,
  setActiveProjectId,
} from '@/features/workspace/projectStorage';
import type { RunItem } from '@/features/workspace/types';

const getRunTitle = (run: RunItem): string => {
  const content = run.request_payload?.content;
  if (typeof content === 'string' && content.trim().length > 0) {
    return content.trim().slice(0, 120);
  }
  return run.id.slice(0, 8);
};

const formatDate = (rawValue: string | null): string => {
  if (!rawValue) return '-';
  const date = new Date(rawValue);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString();
};

export const HistoryGrid: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [projectName, setProjectName] = useState<string>('Project');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    const accessToken = await ensureAuthenticatedAccessToken();
    if (!accessToken) {
      navigate({ to: '/login' });
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const projects = await getProjectsApi(accessToken);
      if (!projects.length) {
        setRuns([]);
        setProjectName(t('history.defaultProject'));
        return;
      }

      const currentProjectId = getActiveProjectId();
      const activeProject = projects.find((project) => project.id === currentProjectId) || projects[0];
      if (currentProjectId !== activeProject.id) {
        setActiveProjectId(activeProject.id);
      }

      setProjectName(activeProject.name);
      const historyRuns = await getProjectHistoryApi(accessToken, activeProject.id);
      setRuns(historyRuns);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.errors.loadFailed'));
    } finally {
      setLoading(false);
    }
  }, [navigate, t]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    const refresh = () => {
      void loadHistory();
    };
    window.addEventListener('project-updated', refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener('project-updated', refresh);
      window.removeEventListener('storage', refresh);
    };
  }, [loadHistory]);

  const rows = useMemo(
    () =>
      runs.map((run) => ({
        id: run.id,
        projectId: run.project_id,
        conversationId: run.conversation_id,
        title: getRunTitle(run),
        url: run.source_url,
        date: formatDate(getRunLastUpdatedAt(run)),
        platforms: run.platforms || [],
      })),
    [runs],
  );

  return (
    <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="h4" sx={{ mb: 1 }}>
          {t('history.title')}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {t('history.subtitle')} ({projectName})
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <TableContainer
        component={Paper}
        sx={{ border: '1px solid', borderColor: 'divider', backgroundImage: 'none', borderRadius: 2 }}
      >
        <Table sx={{ minWidth: 650 }} aria-label={t('layout.historyTableAria')}>
          <TableHead
            sx={(theme) => ({
              bgcolor: theme.palette.mode === 'dark' ? 'rgba(63, 191, 248, 0.08)' : 'rgba(15, 42, 93, 0.06)',
            })}
          >
            <TableRow>
              <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('history.table.title')}</TableCell>
              <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>{t('history.table.date')}</TableCell>
              <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>
                {t('history.table.platforms')}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary' }}>
                {t('history.table.actions')}
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={4}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 4, gap: 1 }}>
                    <CircularProgress size={18} />
                    <Typography variant="body2" color="text.secondary">
                      {t('history.loading')}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4}>
                  <Typography variant="body2" color="text.secondary" sx={{ py: 3, textAlign: 'center' }}>
                    {t('history.empty')}
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow
                  key={row.id}
                  sx={(theme) => ({
                    '&:last-child td, &:last-child th': { border: 0 },
                    '&:hover': {
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(63, 191, 248, 0.06)' : 'rgba(15, 42, 93, 0.04)',
                    },
                  })}
                >
                  <TableCell component="th" scope="row">
                    <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.5 }}>
                      {row.title}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}
                    >
                      <ExternalLink size={12} /> {row.url || '-'}
                    </Typography>
                  </TableCell>
                  <TableCell>{row.date}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                      {row.platforms.length > 0 ? (
                        row.platforms.map((platform) => (
                          <Chip
                            key={platform}
                            label={platform}
                            size="small"
                            variant="outlined"
                            sx={{ borderColor: 'divider', color: 'text.secondary', fontSize: '0.7rem' }}
                          />
                        ))
                      ) : (
                        <Chip
                          label="-"
                          size="small"
                          variant="outlined"
                          sx={{ borderColor: 'divider', color: 'text.secondary', fontSize: '0.7rem' }}
                        />
                      )}
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      variant="text"
                      startIcon={<Eye size={16} />}
                      sx={{ color: 'text.primary', textTransform: 'none' }}
                      onClick={async () => {
                        try {
                          const accessToken = await ensureAuthenticatedAccessToken();
                          if (!accessToken) {
                            navigate({ to: '/login' });
                            return;
                          }

                          const runDetail = await getRunDetailApi(accessToken, row.id);
                          setActiveProjectId(runDetail.project_id);
                          navigate({ to: '/workspace' });
                        } catch (err) {
                          setError(err instanceof Error ? err.message : t('history.errors.openFailed'));
                        }
                      }}
                    >
                      {t('history.table.view')}
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};
