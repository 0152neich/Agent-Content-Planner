import React, { useEffect, useState } from 'react';
import { alpha } from '@mui/material/styles';
import {
  Avatar,
  Box,
  Divider,
  IconButton,
  ListItemButton,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import {
  Check,
  ChevronDown,
  LogOut,
  MoonStar,
  PanelLeft,
  Plus,
  Sun,
  User,
  Wrench,
} from 'lucide-react';
import { Link, useLocation, useNavigate } from '@tanstack/react-router';
import { useTranslation } from 'react-i18next';
import { useColorMode } from '@/theme/colorMode';
import { LanguageSwitcher } from '@/components/Common/LanguageSwitcher';
import { clearAccessToken } from '@/features/auth/authStorage';
import {
  ensureAuthenticatedAccessToken,
  logoutApi,
} from '@/features/auth/api/authApi';
import { ProfileDialog } from '@/features/profile';
import { getProjectsApi } from '@/features/workspace/api/workspaceApi';
import type { ProjectItem } from '@/features/workspace/types';
import {
  getActiveProjectId,
  notifyProjectUpdated,
  setActiveProjectId,
} from '@/features/workspace/projectStorage';

interface SidebarProps {
  onNavigate?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onNavigate, isCollapsed, onToggleCollapse }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const theme = useTheme();
  const navigate = useNavigate();
  const { mode, toggleMode } = useColorMode();
  const isDark = mode === 'dark';
  const sidebarBg = isDark ? '#2a2d33' : '#e5e7eb';

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [projectAnchorEl, setProjectAnchorEl] = useState<null | HTMLElement>(null);
  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectItem | null>(null);

  const openMenu = Boolean(anchorEl);
  const openProjectMenu = Boolean(projectAnchorEl);

  const refreshSidebarData = async () => {
    const token = await ensureAuthenticatedAccessToken();
    if (!token) {
      setProjects([]);
      setActiveProject(null);
      return;
    }
    try {
      const projectList = await getProjectsApi(token);
      setProjects(projectList);
      if (!projectList.length) {
        setActiveProject(null);
        return;
      }

      const currentProjectId = getActiveProjectId();
      const resolvedProject =
        projectList.find((project) => project.id === currentProjectId) || projectList[0];
      if (currentProjectId !== resolvedProject.id) {
        setActiveProjectId(resolvedProject.id);
      }
      setActiveProject(resolvedProject);
    } catch {
      setProjects([]);
      setActiveProject(null);
    }
  };

  useEffect(() => {
    void refreshSidebarData();

    const refresh = () => {
      void refreshSidebarData();
    };

    window.addEventListener('project-updated', refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener('project-updated', refresh);
      window.removeEventListener('storage', refresh);
    };
  }, []);

  const handleOpenMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
  };

  const handleNavigation = (path: string) => {
    handleCloseMenu();
    if (onNavigate) onNavigate();
    navigate({ to: path });
  };

  const handleSelectProject = (project: ProjectItem) => {
    setActiveProjectId(project.id);
    notifyProjectUpdated();
    setProjectAnchorEl(null);
    if (location.pathname !== '/workspace') {
      navigate({ to: '/workspace' });
    }
  };

  const handleLogout = async () => {
    try {
      await logoutApi();
    } catch {
      // no-op
    } finally {
      clearAccessToken();
      handleNavigation('/login');
    }
  };

  const projectName = activeProject?.name || 'My Project';
  const actionIconSx = {
    border: 'none',
    borderRadius: 1.5,
    bgcolor: 'transparent',
    color: 'text.secondary',
    opacity: 0.62,
    '&:hover': {
      opacity: 1,
      color: 'text.primary',
      bgcolor: alpha(theme.palette.background.default, isDark ? 0.45 : 0.72),
    },
  };

  return (
    <Box
      sx={{
        width: isCollapsed ? 64 : 272,
        height: '100%',
        flexShrink: 0,
        borderRight: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: sidebarBg,
        transition: 'width 0.3s ease',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: 1.5, pb: 1.2 }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: isCollapsed ? 'center' : 'space-between',
            mb: 1.2,
          }}
        >
          {!isCollapsed ? (
            <ListItemButton
              onClick={(event) => setProjectAnchorEl(event.currentTarget)}
              sx={{
                borderRadius: 1.5,
                py: 1,
                px: 1.15,
                minHeight: 44,
                gap: 1,
                border: '1px solid transparent',
                bgcolor: 'transparent',
                boxShadow: isDark
                  ? '0 8px 18px rgba(2, 8, 20, 0.35)'
                  : '0 8px 20px rgba(15, 23, 42, 0.08)',
                '&:hover': {
                  borderColor: isDark ? 'rgba(255,255,255,0.14)' : 'rgba(15,23,42,0.18)',
                },
              }}
            >
              <Avatar sx={{ width: 24, height: 24, bgcolor: '#1976d2', fontSize: '0.7rem' }}>
                {projectName.slice(0, 1).toUpperCase()}
              </Avatar>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography noWrap sx={{ fontWeight: 700, fontSize: '0.88rem', lineHeight: 1.1 }}>
                  {projectName}
                </Typography>
              </Box>
              <ChevronDown size={16} />
            </ListItemButton>
          ) : (
            <Tooltip title={projectName} placement="right">
              <IconButton onClick={(event) => setProjectAnchorEl(event.currentTarget)} size="small">
                <Avatar sx={{ width: 28, height: 28, bgcolor: '#1976d2', fontSize: '0.78rem' }}>
                  {projectName.slice(0, 1).toUpperCase()}
                </Avatar>
              </IconButton>
            </Tooltip>
          )}

          <Box
            sx={{
              display: 'flex',
              flexDirection: isCollapsed ? 'column' : 'row',
              gap: 0.6,
              alignItems: 'center',
              p: 0,
            }}
          >
            <Tooltip title={isCollapsed ? t('common.expand') : t('common.collapse')}>
              <IconButton onClick={onToggleCollapse} size="small" sx={actionIconSx}>
                <PanelLeft size={16} />
              </IconButton>
            </Tooltip>
            {!isCollapsed && (
              <>
                <LanguageSwitcher />
                <Tooltip title={isDark ? t('common.lightMode') : t('common.darkMode')}>
                  <IconButton onClick={toggleMode} size="small" sx={actionIconSx}>
                    {isDark ? <Sun size={15} /> : <MoonStar size={15} />}
                  </IconButton>
                </Tooltip>
              </>
            )}
          </Box>
        </Box>
      </Box>

      <Box sx={{ flex: 1, px: isCollapsed ? 1 : 1.5 }}>
        {!isCollapsed && (
          <Typography
            variant="body2"
            sx={{
              color: 'text.secondary',
              px: 1,
              py: 1.4,
            }}
          >
            One campaign, one chat thread.
          </Typography>
        )}
      </Box>

      <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
        <ListItemButton
          onClick={handleOpenMenu}
          sx={{
            borderRadius: 1,
            py: 0.8,
            px: isCollapsed ? 0.5 : 1,
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            border: '1px solid transparent',
            bgcolor: 'transparent',
            '&:hover': {
              bgcolor: isDark ? alpha('#ffffff', 0.06) : alpha('#111827', 0.05),
              borderColor: isDark ? 'rgba(255,255,255,0.14)' : 'rgba(15,23,42,0.18)',
            },
          }}
        >
          <Avatar
            sx={{
              width: 28,
              height: 28,
              mr: isCollapsed ? 0 : 1.5,
              bgcolor: '#4b5563',
              fontSize: '0.75rem',
            }}
          >
            SM
          </Avatar>
          {!isCollapsed && (
            <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' }}>
              <Typography noWrap sx={{ fontWeight: 600, fontSize: '0.8rem', color: 'text.primary', lineHeight: 1.1 }}>
                Sophia Moore
              </Typography>
              <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', lineHeight: 1.1 }}>
                Plus
              </Typography>
            </Box>
          )}
        </ListItemButton>
      </Box>

      <Menu
        anchorEl={projectAnchorEl}
        open={openProjectMenu}
        onClose={() => setProjectAnchorEl(null)}
        PaperProps={{
          sx: {
            width: 290,
            borderRadius: 1,
            border: '1px solid',
            borderColor: 'divider',
            p: 0.5,
          },
        }}
      >
        <Box sx={{ px: 1.5, py: 0.8 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
            Your projects
          </Typography>
        </Box>
        {projects.map((project) => {
          const isActiveProject = activeProject?.id === project.id;
          return (
            <MenuItem
              key={project.id}
              sx={{ borderRadius: 1.5, py: 1.2 }}
              onClick={() => handleSelectProject(project)}
            >
              <Avatar sx={{ width: 34, height: 34, mr: 1.2, bgcolor: '#1976d2' }}>
                {project.name.slice(0, 1).toUpperCase()}
              </Avatar>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography sx={{ fontWeight: 700, lineHeight: 1.15 }}>{project.name}</Typography>
                <Typography noWrap variant="caption" color="text.secondary">
                  {project.source_url || 'No URL'}
                </Typography>
              </Box>
              {isActiveProject && <Check size={16} />}
            </MenuItem>
          );
        })}
        <Divider sx={{ my: 0.8 }} />
        <MenuItem sx={{ borderRadius: 1.5, py: 1.2, gap: 1.2 }} component={Link} to="/welcome">
          <Plus size={16} /> Add new project
        </MenuItem>
        <MenuItem sx={{ borderRadius: 1.5, py: 1.2, gap: 1.2 }}>
          <Wrench size={16} /> Manage projects
        </MenuItem>
      </Menu>

      <Menu
        anchorEl={anchorEl}
        open={openMenu}
        onClose={handleCloseMenu}
        PaperProps={{
          sx: {
            width: 240,
            bgcolor: isDark ? '#1A1A1A' : 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            boxShadow: isDark ? '0 10px 30px rgba(0,0,0,0.5)' : '0 4px 20px rgba(0,0,0,0.08)',
            mb: 1,
          },
        }}
        transformOrigin={{ horizontal: 'left', vertical: 'bottom' }}
        anchorOrigin={{ horizontal: 'left', vertical: 'top' }}
      >
        <Box sx={{ px: 2, py: 1.5, display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Avatar sx={{ width: 36, height: 36, bgcolor: '#4b5563', fontSize: '0.9rem' }}>
            SM
          </Avatar>
          <Box>
            <Typography sx={{ fontWeight: 600, fontSize: '0.9rem', color: 'text.primary', lineHeight: 1.2 }}>
              Sophia Moore
            </Typography>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.secondary', lineHeight: 1.2 }}>
              @anleeyeraly1988
            </Typography>
          </Box>
        </Box>
        <Divider sx={{ mb: 1, borderColor: 'divider' }} />
        <MenuItem
          onClick={() => {
            handleCloseMenu();
            setProfileDialogOpen(true);
          }}
          sx={{ py: 1.2, px: 2, gap: 1.5, color: 'text.primary', fontSize: '0.9rem' }}
        >
          <User size={18} /> {t('common.profile')}
        </MenuItem>
        <Divider sx={{ my: 1, borderColor: 'divider' }} />
        <MenuItem
          onClick={handleLogout}
          sx={{ py: 1.2, px: 2, gap: 1.5, color: 'error.main', fontSize: '0.9rem' }}
        >
          <LogOut size={18} /> {t('common.logout')}
        </MenuItem>
      </Menu>

      <ProfileDialog
        open={profileDialogOpen}
        onClose={() => setProfileDialogOpen(false)}
      />
    </Box>
  );
};
