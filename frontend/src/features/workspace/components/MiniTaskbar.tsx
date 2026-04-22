import React from 'react';
import {
  Avatar,
  Box,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Tooltip,
  useTheme,
} from '@mui/material';
import { LogOut, MoonStar, Plus, Settings2, Sun, User } from 'lucide-react';
import type { UserItem } from '@/features/users/api/userApi';
import { useColorMode } from '@/theme/colorMode';

type MiniTaskbarProps = {
  currentUser: UserItem | null;
  onCreateProject: () => void;
  onOpenProfile: () => void;
  onOpenSettings: () => void;
  onRequestLogout: () => void;
  mobile?: boolean;
};

export const MiniTaskbar: React.FC<MiniTaskbarProps> = ({
  currentUser,
  onCreateProject,
  onOpenProfile,
  onOpenSettings,
  onRequestLogout,
  mobile = false,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const { toggleMode } = useColorMode();
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);
  const openMenu = Boolean(anchorEl);

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
