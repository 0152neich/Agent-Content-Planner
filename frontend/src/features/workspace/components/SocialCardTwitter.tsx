import React from 'react';
import { Box, Paper, Typography, Avatar, IconButton } from '@mui/material';
import { MoreHorizontal, MessageCircle, Repeat2, Heart, BarChart3, Share } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type SocialCardTwitterProps = {
  content?: string;
};

export const SocialCardTwitter: React.FC<SocialCardTwitterProps> = ({ content }) => {
  const { t } = useTranslation();

  const resolvedContent = content || t('workspace.results.socialMock.twitter');

  const isOverLimit = resolvedContent.length > 280;

  return (
    <Box sx={{ maxWidth: 600, width: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography
          variant="body2"
          sx={{
            color: isOverLimit ? 'error.main' : 'text.secondary',
            fontWeight: 600
          }}
        >
          {resolvedContent.length} / 280 {t('workspace.results.characters')}
        </Typography>
      </Box>

      <Paper
        sx={(theme) => ({
          p: 2,
          bgcolor: theme.palette.mode === 'dark' ? 'rgba(11, 22, 43, 0.95)' : 'rgba(255,255,255,0.92)',
          borderRadius: 4,
          border: '1px solid',
          borderColor: 'divider',
        })}
      >
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
          <Avatar src="https://ui-avatars.com/api/?name=AI&background=1DA1F2&color=fff" sx={{ width: 40, height: 40, mr: 1.5 }} />
          <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
                AI Content Planner
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                {t('common.twitterHandle')} · {t('workspace.results.2m')}
              </Typography>
            </Box>

            {/* Content */}
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', color: 'text.primary', mt: 0.5, lineHeight: 1.5 }}>
              {resolvedContent}
            </Typography>
          </Box>
          <IconButton size="small" sx={{ color: 'text.secondary' }}>
            <MoreHorizontal size={18} />
          </IconButton>
        </Box>

        {/* Actions */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2, pl: 6.5, pr: 2 }}>
          {[
            { icon: MessageCircle, count: '12' },
            { icon: Repeat2, count: '45' },
            { icon: Heart, count: '312' },
            { icon: BarChart3, count: '1.2K' },
            { icon: Share, count: '' },
          ].map((action, i) => (
            <Box
              key={i}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                color: 'text.secondary',
                cursor: 'pointer',
                '&:hover': { color: '#1DA1F2' }
              }}
            >
              <action.icon size={18} />
              {action.count && <Typography variant="caption">{action.count}</Typography>}
            </Box>
          ))}
        </Box>
      </Paper>
    </Box>
  );
};
