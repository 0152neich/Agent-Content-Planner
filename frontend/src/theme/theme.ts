import { alpha, createTheme } from '@mui/material/styles';
import type { PaletteMode, Theme } from '@mui/material';
import '@fontsource/spline-sans/300.css';
import '@fontsource/spline-sans/400.css';
import '@fontsource/spline-sans/500.css';
import '@fontsource/spline-sans/600.css';
import '@fontsource/spline-sans/700.css';

const getTokens = (mode: PaletteMode) => {
  if (mode === 'light') {
    return {
      bg: '#f6fbff',
      paper: '#ffffff',
      border: '#d8e7f5',
      textPrimary: '#0f2238',
      textSecondary: '#52708d',
      primary: '#0f7bdc',
      primarySoft: '#e8f4ff',
      bodyGradient: 'radial-gradient(circle at 30% 0%, #ffffff 0%, #eef7ff 48%, #e1f1ff 100%)',
    };
  }

  return {
    bg: '#0D0D0D',
    paper: '#1A1A1A',
    border: '#2D2D2D',
    textPrimary: '#ffffff',
    textSecondary: '#a1a1aa',
    primary: '#00A3FF',
    primarySoft: 'rgba(0, 163, 255, 0.16)',
    bodyGradient: 'none',
  };
};

export const getAppTheme = (mode: PaletteMode): Theme => {
  const t = getTokens(mode);
  const isDark = mode === 'dark';

  return createTheme({
    palette: {
      mode,
      background: {
        default: t.bg,
        paper: t.paper,
      },
      primary: {
        main: t.primary,
      },
      secondary: {
        main: isDark ? '#1f7ab6' : '#1f96df',
      },
      error: {
        main: '#ef4444',
      },
      success: {
        main: '#16a34a',
      },
      text: {
        primary: t.textPrimary,
        secondary: t.textSecondary,
      },
      divider: t.border,
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "-apple-system", "BlinkMacSystemFont", "Segoe UI", sans-serif',
      h1: { fontFamily: '"Inter", sans-serif', fontWeight: 700, letterSpacing: '-0.02em' },
      h2: { fontFamily: '"Inter", sans-serif', fontWeight: 700, letterSpacing: '-0.02em' },
      h3: { fontFamily: '"Inter", sans-serif', fontWeight: 600, letterSpacing: '-0.01em' },
      h4: { fontFamily: '"Inter", sans-serif', fontWeight: 600, letterSpacing: '-0.01em' },
      h5: { fontFamily: '"Inter", sans-serif', fontWeight: 600 },
      h6: { fontFamily: '"Inter", sans-serif', fontWeight: 600 },
      button: { textTransform: 'none', fontWeight: 600, letterSpacing: '0.01em' },
      body1: { letterSpacing: '0.01em' },
      body2: { letterSpacing: '0.01em' },
    },
    shape: {
      borderRadius: 16,
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: t.bg,
            backgroundImage: t.bodyGradient,
            backgroundAttachment: 'fixed',
            minHeight: '100vh',
            backgroundRepeat: 'no-repeat',
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 999,
            padding: '10px 20px',
            transition: 'all 0.26s cubic-bezier(0.4, 0, 0.2, 1)',
          },
          containedPrimary: {
            background: isDark
              ? 'linear-gradient(to right, #007AFF, #00C2FF)'
              : 'linear-gradient(120deg, #0f7bdc 0%, #2cb7ff 100%)',
            color: '#ffffff',
            fontWeight: 700,
            border: 'none',
            boxShadow: isDark
              ? '0 0 20px rgba(0, 163, 255, 0.5)'
              : '0 6px 16px rgba(15, 123, 220, 0.24)',
            '&:hover': {
              transform: 'translateY(-1px)',
              boxShadow: isDark
                ? '0 0 25px rgba(0, 163, 255, 0.65)'
                : '0 10px 22px rgba(15, 123, 220, 0.32)',
            },
          },
          outlined: {
            borderColor: alpha(t.textSecondary, isDark ? 0.35 : 0.3),
            color: t.textPrimary,
            backgroundColor: alpha(isDark ? '#0d1f3a' : '#ffffff', isDark ? 0.36 : 0.84),
            '&:hover': {
              borderColor: alpha(t.primary, 0.6),
              backgroundColor: alpha(t.primary, isDark ? 0.12 : 0.08),
            },
          },
        },
        defaultProps: {
          disableElevation: true,
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: t.paper,
            border: `1px solid ${t.border}`,
            boxShadow: isDark
              ? '0 10px 30px rgba(0, 0, 0, 0.5)'
              : '0 10px 30px rgba(18, 98, 166, 0.08)',
            borderRadius: 16,
          },
        },
      },
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              backgroundColor: isDark ? '#121212' : alpha('#ffffff', 0.95),
              transition: 'border-color 0.2s, box-shadow 0.2s, background-color 0.2s',
              '& fieldset': {
                borderColor: t.border,
              },
              '&:hover fieldset': {
                borderColor: isDark ? '#007AFF' : alpha(t.primary, 0.45),
              },
              '&.Mui-focused fieldset': {
                borderColor: isDark ? '#00A3FF' : t.primary,
              },
              '&.Mui-focused': {
                backgroundColor: isDark ? '#121212' : '#ffffff',
              },
            },
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            color: t.textSecondary,
            '&.Mui-selected': {
              color: t.textPrimary,
            },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderColor: alpha(t.primary, 0.3),
            color: t.textSecondary,
          },
        },
      },
      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: t.paper,
            borderRight: `1px solid ${t.border}`,
          },
        },
      },
    },
  });
};
