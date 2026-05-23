import React from 'react';
import { Box, Dialog, IconButton, Typography } from '@mui/material';
import { X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { ProfileForm } from './ProfileForm';

type ProfileDialogProps = {
  open: boolean;
  onClose: () => void;
};

export const ProfileDialog: React.FC<ProfileDialogProps> = ({ open, onClose }) => {
  const { t } = useTranslation();

  return (
    <Dialog
    open={open}
    onClose={onClose}
    scroll="paper"
    fullWidth
    maxWidth="md"
    PaperProps={{
      sx: {
        borderRadius: 2,
        overflow: 'hidden',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column',
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
      <Typography sx={{ fontWeight: 700 }}>{t('profile.dialog.title')}</Typography>
      <IconButton onClick={onClose} size="small" aria-label={t('profile.dialog.closeAria')}>
        <X size={18} />
      </IconButton>
    </Box>

    <Box
      sx={{
        p: { xs: 1.4, md: 2 },
        overflowY: 'auto',
        minHeight: 0,
      }}
    >
      <ProfileForm embedded hideHeader onSaved={onClose} />
    </Box>
  </Dialog>
  );
};
