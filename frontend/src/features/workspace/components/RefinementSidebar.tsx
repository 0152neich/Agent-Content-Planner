import React, { useEffect, useMemo, useRef } from 'react';
import { Box, Typography, useTheme } from '@mui/material';
import type { WorkspaceChatMessage } from '../types';
import { RefinementComposer } from './RefinementComposer';
import { RefinementMessageList } from './RefinementMessageList';

type ModelOption = {
  value: string;
  label: string;
};

type RefinementSidebarProps = {
  messages: WorkspaceChatMessage[];
  prompt: string;
  selectedModel: string;
  modelOptions: ModelOption[];
  suggestions: string[];
  loading: boolean;
  refining: boolean;
  showSuggestionChips: boolean;
  onChangePrompt: (value: string) => void;
  onSelectModel: (value: string) => void;
  onSubmitPrompt: () => void;
  onCancelPrompt: () => void;
  onSelectSuggestion: (value: string) => void;
};

export const RefinementSidebar: React.FC<RefinementSidebarProps> = ({
  messages,
  prompt,
  selectedModel,
  modelOptions,
  suggestions,
  loading,
  refining,
  showSuggestionChips,
  onChangePrompt,
  onSelectModel,
  onSubmitPrompt,
  onCancelPrompt,
  onSelectSuggestion,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const previousMessageCountRef = useRef(messages.length);

  const lastMessageKey = useMemo(() => {
    const last = messages[messages.length - 1];
    if (!last) {
      return 'empty';
    }
    return `${last.id}:${last.content.length}:${last.isLoading ? 'loading' : 'done'}`;
  }, [messages]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) {
      return;
    }
    const hasNewMessage = messages.length !== previousMessageCountRef.current;
    previousMessageCountRef.current = messages.length;
    container.scrollTo({
      top: container.scrollHeight,
      behavior: hasNewMessage ? 'smooth' : 'auto',
    });
  }, [messages.length, lastMessageKey]);

  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: isDark ? '#111418' : '#f7fafc',
        minHeight: 0,
      }}
    >
      <Box
        sx={{
          px: 1.6,
          py: 1,
          position: 'sticky',
          top: 0,
          zIndex: 3,
          borderBottom: '1px solid',
          borderColor: isDark ? 'rgba(255,255,255,0.08)' : '#e3ebf4',
          bgcolor: isDark ? 'rgba(17,20,24,0.82)' : 'rgba(247,250,252,0.84)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <Typography sx={{ fontWeight: 700, fontSize: '0.88rem', letterSpacing: '0.01em' }}>
          Refinement Chat
        </Typography>
      </Box>

    <Box ref={scrollContainerRef} sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: 1.35, py: 1.1 }}>
      <RefinementMessageList
        messages={messages}
        showSuggestionChips={showSuggestionChips}
        suggestions={suggestions}
        refining={refining || loading}
        onSelectSuggestion={onSelectSuggestion}
      />
    </Box>

    <Box
      sx={{
        px: 1.2,
        pb: 0.9,
        pt: 0.5,
        position: 'sticky',
        bottom: 0,
        zIndex: 3,
        borderTop: '1px solid',
        borderColor: isDark ? 'rgba(255,255,255,0.08)' : '#e3ebf4',
        bgcolor: isDark ? 'rgba(17,20,24,0.82)' : 'rgba(247,250,252,0.84)',
        backdropFilter: 'blur(10px)',
      }}
    >
      <RefinementComposer
        value={prompt}
        selectedModel={selectedModel}
        modelOptions={modelOptions}
        refining={refining}
        disabled={loading || refining}
        onChangeValue={onChangePrompt}
        onSelectModel={onSelectModel}
        onSubmit={onSubmitPrompt}
        onCancel={onCancelPrompt}
      />
    </Box>
  </Box>
  );
};
