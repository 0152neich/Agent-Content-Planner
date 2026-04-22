import React from 'react';
import { Box, Paper, Typography, Avatar, Button, IconButton } from '@mui/material';
import { MoreHorizontal, ThumbsUp, MessageSquare, Share2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type SocialCardLinkedInProps = {
  content?: string;
};

export const SocialCardLinkedIn: React.FC<SocialCardLinkedInProps> = ({ content }) => {
  const { t } = useTranslation();

  const resolvedContent = content || t('workspace.results.socialMock.linkedin');

  return (
    <Box sx={{ maxWidth: 600, width: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper
        sx={(theme) => ({
          p: 2,
          bgcolor: theme.palette.mode === 'dark' ? 'rgba(15, 29, 51, 0.95)' : 'rgba(255,255,255,0.92)',
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
        })}
      >
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Avatar src="https://ui-avatars.com/api/?name=AI&background=0D8ABC&color=fff" sx={{ width: 48, height: 48, mr: 1.5 }} />
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
              AI Content Planner
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.8rem' }}>
              Automated Marketing Solutions
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', fontSize: '0.75rem', display: 'flex', alignItems: 'center' }}>
              {t('workspace.results.justNow')} • 🌐
            </Typography>
          </Box>
          <IconButton size="small" sx={{ color: 'text.secondary' }}>
            <MoreHorizontal size={20} />
          </IconButton>
        </Box>

        {/* Content */}
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', mb: 2, lineHeight: 1.6 }}>
          {resolvedContent}
        </Typography>

        {/* Stats */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'text.secondary', fontSize: '0.75rem', py: 1, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ bgcolor: '#0a66c2', borderRadius: '50%', p: 0.4, display: 'flex' }}>
              <ThumbsUp size={10} color="#fff" fill="#fff" />
            </Box>
            128
          </Box>
          <Box>
            24 {t('workspace.results.comments')} • 5 {t('workspace.results.shares')}
          </Box>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 1, px: 2 }}>
          {[
            { icon: ThumbsUp, label: t('workspace.results.like') },
            { icon: MessageSquare, label: t('workspace.results.comment') },
            { icon: Share2, label: t('workspace.results.share') },
          ].map((action, i) => (
            <Button
              key={i}
              variant="text"
              startIcon={<action.icon size={20} />}
              sx={{ color: 'text.secondary', textTransform: 'none', fontWeight: 600, '&:hover': { bgcolor: 'rgba(63, 191, 248, 0.1)' } }}
            >
              {action.label}
            </Button>
          ))}
        </Box>
      </Paper>
    </Box>
  );
};
