import React from 'react';
import { Box, Dialog, IconButton, Typography } from '@mui/material';
import { X } from 'lucide-react';
import { ProjectSettingsForm } from './ProjectSettingsForm';

type ProjectSettingsDialogProps = {
  open: boolean;
  onClose: () => void;
};

export const ProjectSettingsDialog: React.FC<ProjectSettingsDialogProps> = ({
  open,
  onClose,
}) => (
  <Dialog
    open={open}
    onClose={onClose}
    fullWidth
    maxWidth="md"
    PaperProps={{
      sx: {
        borderRadius: 2,
        overflow: 'hidden',
      },
    }}
  >
    <Box
      sx={{
        px: 2.4,
        py: 1.2,
        borderBottom: '1px solid',
        borderColor: 'divider',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <Typography sx={{ fontWeight: 700 }}>Project settings</Typography>
      <IconButton onClick={onClose} size="small" aria-label="Close project settings dialog">
        <X size={18} />
      </IconButton>
    </Box>
    <Box sx={{ p: { xs: 1.4, md: 2 } }}>
      <ProjectSettingsForm embedded hideHeader onSaved={onClose} />
    </Box>
  </Dialog>
);
