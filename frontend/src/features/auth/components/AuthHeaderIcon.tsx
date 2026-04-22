import React from 'react';
import { alpha } from '@mui/material/styles';
import { Box } from '@mui/material';
import type { LucideIcon } from 'lucide-react';

interface AuthHeaderIconProps {
  icon: LucideIcon;
}

export const AuthHeaderIcon: React.FC<AuthHeaderIconProps> = ({ icon: Icon }) => {
  return (
    <Box
      sx={(theme) => {
        const isDark = theme.palette.mode === 'dark';
        return {
          width: { xs: 80, md: 88 },
          height: { xs: 80, md: 88 },
          borderRadius: '50%',
          border: '1px solid',
          borderColor: 'divider',
          bgcolor: isDark ? 'rgba(14, 165, 233, 0.09)' : 'rgba(15, 23, 42, 0.08)',
          color: 'primary.main',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          mb: 3,
          position: 'relative',
          boxShadow: isDark
            ? '0 0 0 8px rgba(63, 191, 248, 0.07), 0 14px 30px rgba(9, 45, 86, 0.45)'
            : '0 0 0 7px rgba(12, 43, 99, 0.06), 0 10px 22px rgba(15, 23, 42, 0.12)',
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: { xs: 10, md: 11 },
            borderRadius: '50%',
            border: `1px solid ${alpha(theme.palette.primary.main, isDark ? 0.35 : 0.28)}`,
          },
        };
      }}
    >
      <Icon size={34} />
    </Box>
  );
};
