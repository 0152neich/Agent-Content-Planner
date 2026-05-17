import React from 'react';
import {
  Avatar,
  Box,
  Divider,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
  Tooltip,
  useTheme,
} from '@mui/material';
import { CalendarClock, Check, FolderOpen, LogOut, MoonStar, Plus, Settings2, Sun, User } from 'lucide-react';
import type { UserItem } from '@/features/users/api/userApi';
import type { ProjectItem } from '@/features/workspace/types';
import { useColorMode } from '@/theme/colorMode';

type MiniTaskbarProps = {
  currentUser: UserItem | null;
  onCreateProject: () => void;
  onOpenProfile: () => void;
  onOpenSettings: () => void;
  onRequestLogout: () => void;
  mobile?: boolean;
  mode?: 'recreate' | 'autopost';
  onSwitchMode?: (mode: 'recreate' | 'autopost') => void;
  projects?: ProjectItem[];
  activeProjectId?: string | null;
  onSelectProject?: (projectId: string) => void;
};

export const MiniTaskbar: React.FC<MiniTaskbarProps> = ({
  currentUser,
  onCreateProject,
  onOpenProfile,
  onOpenSettings,
  onRequestLogout,
  mobile = false,
  mode = 'recreate',
  onSwitchMode,
  projects = [],
  activeProjectId = null,
  onSelectProject,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const { toggleMode } = useColorMode();
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);
  const [projectAnchorEl, setProjectAnchorEl] = React.useState<HTMLElement | null>(null);
  const openMenu = Boolean(anchorEl);
  const openProjectMenu = Boolean(projectAnchorEl);

  const avatarLabel = (currentUser?.full_name || currentUser?.user_name || currentUser?.email || 'U')
    .trim()
    .slice(0, 1)
    .toUpperCase();

  const closeMenu = () => setAnchorEl(null);

  return (
    <Box
      sx={{
        width: mobile ? '100%' : 56,
        height: mobile ? 52 : '100%',
        borderRight: mobile ? 'none' : '1px solid',
        borderBottom: mobile ? '1px solid' : 'none',
        borderColor: isDark ? 'rgba(255,255,255,0.12)' : '#d7e2ef',
        bgcolor: isDark ? '#151515' : '#f4f8fc',
        display: 'flex',
        flexDirection: mobile ? 'row' : 'column',
        alignItems: 'center',
        justifyContent: mobile ? 'space-between' : 'space-between',
        py: mobile ? 0.4 : 0.9,
        px: mobile ? 0.8 : 0.5,
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: mobile ? 'row' : 'column', gap: 0.8 }}>
        <Tooltip title="Create project" placement={mobile ? 'bottom' : 'right'}>
          <IconButton
            size="small"
            aria-label="Create project"
            onClick={onCreateProject}
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              color: isDark ? '#dde5ef' : '#24364d',
              bgcolor: 'transparent',
              transition: 'all 0.18s ease',
              '&:hover': {
                bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,123,220,0.1)',
                color: isDark ? '#ffffff' : '#0f63b5',
              },
              '&:focus-visible': {
                outline: '2px solid #0f7bdc',
                outlineOffset: 1,
              },
            }}
          >
            <Plus size={16} />
          </IconButton>
        </Tooltip>
        <Tooltip title={isDark ? 'Switch to light mode' : 'Switch to dark mode'} placement={mobile ? 'bottom' : 'right'}>
          <IconButton
            size="small"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            onClick={toggleMode}
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              color: isDark ? '#dde5ef' : '#24364d',
              bgcolor: 'transparent',
              transition: 'all 0.18s ease',
              '&:hover': {
                bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,123,220,0.1)',
                color: isDark ? '#ffffff' : '#0f63b5',
              },
              '&:focus-visible': {
                outline: '2px solid #0f7bdc',
                outlineOffset: 1,
              },
            }}
          >
            {isDark ? <Sun size={16} /> : <MoonStar size={16} />}
          </IconButton>
        </Tooltip>
        <Tooltip title="Projects" placement={mobile ? 'bottom' : 'right'}>
          <IconButton
            size="small"
            aria-label="Open project menu"
            onClick={(event) => setProjectAnchorEl(event.currentTarget)}
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              color: mode === 'recreate' ? '#0f63b5' : isDark ? '#dde5ef' : '#24364d',
              bgcolor: mode === 'recreate'
                ? isDark
                  ? 'rgba(23,130,255,0.20)'
                  : 'rgba(15,123,220,0.16)'
                : 'transparent',
              transition: 'all 0.18s ease',
              '&:hover': {
                bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,123,220,0.1)',
                color: isDark ? '#ffffff' : '#0f63b5',
              },
            }}
          >
            <FolderOpen size={16} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Auto-Post" placement={mobile ? 'bottom' : 'right'}>
          <IconButton
            size="small"
            aria-label="Auto-Post"
            onClick={() => onSwitchMode?.('autopost')}
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1.5,
              color: mode === 'autopost' ? '#0f63b5' : isDark ? '#dde5ef' : '#24364d',
              bgcolor: mode === 'autopost'
                ? isDark
                  ? 'rgba(23,130,255,0.20)'
                  : 'rgba(15,123,220,0.16)'
                : 'transparent',
              transition: 'all 0.18s ease',
              '&:hover': {
                bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,123,220,0.1)',
                color: isDark ? '#ffffff' : '#0f63b5',
              },
            }}
          >
            <CalendarClock size={16} />
          </IconButton>
        </Tooltip>
      </Box>

      <Tooltip title="Account menu" placement={mobile ? 'bottom' : 'right'}>
        <IconButton
          size="small"
          aria-label="Open account menu"
          onClick={(event) => setAnchorEl(event.currentTarget)}
          sx={{
            width: 36,
            height: 36,
            borderRadius: 1.5,
            color: isDark ? '#e6edf7' : '#1d3552',
            bgcolor: 'transparent',
            transition: 'all 0.18s ease',
            '&:hover': {
              bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,123,220,0.12)',
              color: isDark ? '#ffffff' : '#0f63b5',
            },
            '&:focus-visible': {
              outline: '2px solid #0f7bdc',
              outlineOffset: 1,
            },
          }}
        >
          <Avatar
            src={currentUser?.avatar_url || undefined}
            sx={{
              width: 28,
              height: 28,
              bgcolor: isDark ? '#223248' : '#dbe8f6',
              color: isDark ? '#f1f6fc' : '#19314e',
              fontSize: '0.77rem',
              fontWeight: 700,
            }}
          >
            {avatarLabel}
          </Avatar>
        </IconButton>
      </Tooltip>

      <Menu
        open={openProjectMenu}
        anchorEl={projectAnchorEl}
        onClose={() => setProjectAnchorEl(null)}
        anchorOrigin={{ vertical: mobile ? 'bottom' : 'top', horizontal: 'right' }}
        transformOrigin={{ vertical: mobile ? 'top' : 'bottom', horizontal: 'left' }}
        PaperProps={{
          sx: {
            width: 280,
            borderRadius: 1.5,
            border: '1px solid',
            borderColor: isDark ? 'rgba(255,255,255,0.15)' : '#d7e2ef',
            p: 0.5,
          },
        }}
      >
        <Box sx={{ px: 1.2, py: 0.8 }}>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 700 }}>
            Your projects
          </Typography>
        </Box>
        {!projects.length ? (
          <MenuItem disabled sx={{ borderRadius: 1.2 }}>
            <ListItemText primary="No projects yet" />
          </MenuItem>
        ) : null}
        {projects.map((project) => {
          const isActiveProject = activeProjectId === project.id;
          return (
            <MenuItem
              key={project.id}
              sx={{ borderRadius: 1.2, py: 1.1 }}
              onClick={() => {
                setProjectAnchorEl(null);
                onSelectProject?.(project.id);
              }}
            >
              <Avatar sx={{ width: 30, height: 30, mr: 1.1, bgcolor: '#1976d2', fontSize: '0.75rem' }}>
                {project.name.slice(0, 1).toUpperCase()}
              </Avatar>
              <ListItemText
                primary={project.name}
                secondary={project.source_url || 'No URL'}
                primaryTypographyProps={{ fontWeight: 700, fontSize: '0.85rem' }}
                secondaryTypographyProps={{ noWrap: true, fontSize: '0.72rem' }}
              />
              {isActiveProject ? <Check size={16} /> : null}
            </MenuItem>
          );
        })}
        <Divider sx={{ my: 0.5 }} />
        <MenuItem
          sx={{ borderRadius: 1.2, py: 1 }}
          onClick={() => {
            setProjectAnchorEl(null);
            onCreateProject();
          }}
        >
          <ListItemIcon>
            <Plus size={16} />
          </ListItemIcon>
          <ListItemText primary="Add new project" />
        </MenuItem>
      </Menu>

      <Menu
        open={openMenu}
        anchorEl={anchorEl}
        onClose={closeMenu}
        anchorOrigin={{ vertical: mobile ? 'bottom' : 'top', horizontal: mobile ? 'right' : 'right' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
      >
        <MenuItem
          onClick={() => {
            closeMenu();
            onOpenProfile();
          }}
        >
          <ListItemIcon>
            <User size={16} />
          </ListItemIcon>
          <ListItemText primary="Profile" />
        </MenuItem>
        <MenuItem
          onClick={() => {
            closeMenu();
            onOpenSettings();
          }}
        >
          <ListItemIcon>
            <Settings2 size={16} />
          </ListItemIcon>
          <ListItemText primary="Settings" />
        </MenuItem>
        <MenuItem
          onClick={() => {
            closeMenu();
            onRequestLogout();
          }}
          sx={{ color: '#b91c1c' }}
        >
          <ListItemIcon sx={{ color: '#b91c1c' }}>
            <LogOut size={16} />
          </ListItemIcon>
          <ListItemText primary="Logout" />
        </MenuItem>
      </Menu>
    </Box>
  );
};
