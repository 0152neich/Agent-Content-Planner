import React from 'react';
import { Box, CircularProgress, Typography, useTheme } from '@mui/material';
import type { WorkspaceChatMessage } from '../types';
import { MarkdownBlock } from './MarkdownBlock';
import { SuggestionChips } from './SuggestionChips';

type RefinementMessageListProps = {
  messages: WorkspaceChatMessage[];
  showSuggestionChips: boolean;
  suggestions: string[];
  refining: boolean;
  onSelectSuggestion: (prompt: string) => void;
};

export const RefinementMessageList: React.FC<RefinementMessageListProps> = ({
  messages,
  showSuggestionChips,
  suggestions,
  refining,
  onSelectSuggestion,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1,
        px: 0.2,
      }}
    >
      {showSuggestionChips && (
        <SuggestionChips
          suggestions={suggestions}
          disabled={refining}
          onSelect={onSelectSuggestion}
        />
      )}
      {messages.map((message, index) => {
        const isUser = message.role === 'user';
        const isSystem = message.role === 'system';
        const isAssistant = message.role === 'assistant';
        return (
          <Box
            key={`${message.id}-${index}`}
            sx={{
              alignSelf: isSystem ? 'center' : isUser ? 'flex-end' : 'flex-start',
              width: isSystem ? '100%' : 'fit-content',
              maxWidth: '92%',
              px: isSystem ? 0.4 : 1.15,
              py: isSystem ? 0.15 : 0.95,
              borderRadius: isSystem ? 0 : 1.4,
              border: isSystem || isAssistant ? 'none' : '1px solid',
              borderColor: isUser
                ? (isDark ? 'rgba(70,169,255,0.78)' : '#2f90e8')
                : isDark
                  ? 'rgba(255,255,255,0.15)'
                  : 'rgba(15, 23, 42, 0.12)',
              bgcolor: isSystem
                ? 'transparent'
                : isUser
                  ? (isDark ? 'rgba(21,109,187,0.95)' : '#1b83dc')
                  : isDark
                    ? 'rgba(255,255,255,0.04)'
                    : '#ffffff',
              color: isSystem ? 'text.secondary' : isUser ? '#ffffff' : 'text.primary',
              boxShadow: isSystem
                ? 'none'
                : isUser
                  ? (isDark
                    ? '0 6px 18px rgba(2, 35, 66, 0.55)'
                    : '0 8px 20px rgba(27, 131, 220, 0.25)')
                  : 'none',
              textAlign: isSystem ? 'center' : 'left',
            }}
          >
            {message.isLoading ? (
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.8 }}>
                <CircularProgress size={14} sx={{ mt: 0.35, flexShrink: 0 }} />
                {isUser ? (
                  <Typography sx={{ fontSize: '0.9rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
                    {message.content}
                  </Typography>
                ) : isSystem ? (
                  <Typography
                    sx={{
                      fontSize: '0.82rem',
                      fontStyle: 'italic',
                      opacity: 0.72,
                      lineHeight: 1.35,
                    }}
                  >
                    {message.content}
                  </Typography>
                ) : message.content ? (
                  <Box sx={{ color: 'text.primary', '& p:last-child': { mb: 0 } }}>
                    <MarkdownBlock value={message.content} />
                  </Box>
                ) : (
                  <Typography sx={{ fontSize: '0.9rem', lineHeight: 1.55, opacity: 0.72 }}>
                    Thinking...
                  </Typography>
                )}
              </Box>
            ) : isSystem ? (
              <Typography
                sx={{
                  fontSize: '0.82rem',
                  fontStyle: 'italic',
                  opacity: 0.72,
                  lineHeight: 1.35,
                }}
              >
                {message.content}
              </Typography>
            ) : isUser ? (
              <Typography sx={{ fontSize: '0.9rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
                {message.content}
              </Typography>
            ) : (
              <Box sx={{ '& p:last-child': { mb: 0 } }}>
                <MarkdownBlock value={message.content} />
              </Box>
            )}
          </Box>
        );
      })}
    </Box>
  );
};
