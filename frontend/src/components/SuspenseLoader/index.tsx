import React, { Suspense } from 'react';
import { Box, CircularProgress } from '@mui/material';

interface SuspenseLoaderProps {
  children: React.ReactNode;
}

export const SuspenseLoader: React.FC<SuspenseLoaderProps> = ({ children }) => {
  return (
    <Suspense
      fallback={
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '200px',
            width: '100%',
          }}
        >
          <CircularProgress size={24} sx={{ color: 'text.secondary' }} />
        </Box>
      }
    >
      {children}
    </Suspense>
  );
};
