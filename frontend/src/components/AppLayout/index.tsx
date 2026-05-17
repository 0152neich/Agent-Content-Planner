import React, { useState } from 'react';
import { alpha } from '@mui/material/styles';
import { Box, Drawer, IconButton, Typography, useMediaQuery, useTheme } from '@mui/material';
import { MoonStar, PanelLeft, Sun } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { useSnackbar } from './SnackbarContext';
import { useColorMode } from '@/theme/colorMode';

export { useSnackbar };

export const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { mode, toggleMode } = useColorMode();
  const isDark = mode === 'dark';

  const toggleSidebar = () => setSidebarCollapsed(!sidebarCollapsed);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: { xs: 'column', md: 'row' },
        height: '100dvh',
        minHeight: '100dvh',
        width: '100vw',
        bgcolor: 'background.default',
        overflow: 'hidden',
      }}
    >
      {isMobile ? (
        <>
          <Drawer
            anchor="left"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            PaperProps={{
              sx: {
                width: 264,
                bgcolor: 'background.paper',
              },
            }}
          >
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </Drawer>

          <Box
            sx={{
              position: 'sticky',
              top: 0,
              zIndex: 1200,
              width: '100%',
              height: 64,
              px: 2,
              borderBottom: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 600 }}>
              Content Planner
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <IconButton
                onClick={toggleMode}
                size="small"
                sx={{
                  border: '1px solid',
                  borderColor: 'divider',
                  bgcolor: alpha(theme.palette.background.default, isDark ? 0.3 : 0.4),
                }}
              >
                {isDark ? <Sun size={16} /> : <MoonStar size={16} />}
              </IconButton>
              <IconButton onClick={() => setMobileOpen(true)} aria-label="Open navigation">
                <PanelLeft size={20} />
              </IconButton>
            </Box>
          </Box>
        </>
      ) : (
        <Sidebar isCollapsed={sidebarCollapsed} onToggleCollapse={toggleSidebar} />
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          p: { xs: 2, md: 4 },
          overflowY: 'auto',
          minHeight: 0,
          transition: 'all 0.3s ease',
        }}
      >
        <Box sx={{ width: '100%', maxWidth: '1200px' }}>{children}</Box>
      </Box>
    </Box>
  );
};
