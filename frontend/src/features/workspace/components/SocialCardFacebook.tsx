import React from 'react';
import { Box, Paper, Typography, Avatar, Button, IconButton } from '@mui/material';
import { MoreHorizontal, ThumbsUp, MessageSquare, Share2, Globe2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type SocialCardFacebookProps = {
  content?: string;
};

export const SocialCardFacebook: React.FC<SocialCardFacebookProps> = ({ content }) => {
  const { t } = useTranslation();

  const resolvedContent = content || t('workspace.results.socialMock.facebook');

  return (
    <Box sx={{ maxWidth: 600, width: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper
        sx={(theme) => ({
          pt: 2,
          pb: 1,
          bgcolor: theme.palette.mode === 'dark' ? 'rgba(15, 29, 51, 0.95)' : 'rgba(255,255,255,0.92)',
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
        })}
      >
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5, px: 2 }}>
          <Avatar src="https://ui-avatars.com/api/?name=AI&background=1877F2&color=fff" sx={{ width: 40, height: 40, mr: 1.5 }} />
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.primary', lineHeight: 1.2 }}>
              AI Content Planner
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {t('workspace.results.15mins')} <Globe2 size={12} />
            </Typography>
          </Box>
          <IconButton size="small" sx={{ color: 'text.secondary' }}>
            <MoreHorizontal size={20} />
          </IconButton>
        </Box>

        {/* Content */}
        <Box sx={{ px: 2, pb: 2 }}>
          <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', color: 'text.primary', fontSize: '15px' }}>
            {resolvedContent}
          </Typography>
        </Box>

        {/* Stats */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'text.secondary', fontSize: '15px', px: 2, pb: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ bgcolor: '#1877f2', borderRadius: '50%', p: 0.4, display: 'flex' }}>
              <ThumbsUp size={12} color="#fff" fill="#fff" />
            </Box>
            642
          </Box>
          <Box>
            89 {t('workspace.results.comments')} • 45 {t('workspace.results.shares')}
          </Box>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 0.5, px: 2 }}>
          {[
            { icon: ThumbsUp, label: t('workspace.results.like') },
            { icon: MessageSquare, label: t('workspace.results.comment') },
            { icon: Share2, label: t('workspace.results.share') },
          ].map((action, i) => (
            <Button
              key={i}
              variant="text"
              startIcon={<action.icon size={20} />}
              sx={{
                color: 'text.secondary',
                textTransform: 'none',
                fontWeight: 600,
                flex: 1,
                borderRadius: 1,
                py: 1,
                '&:hover': { bgcolor: 'rgba(63, 191, 248, 0.1)' }
              }}
            >
              {action.label}
            </Button>
          ))}
        </Box>
      </Paper>
    </Box>
  );
};
