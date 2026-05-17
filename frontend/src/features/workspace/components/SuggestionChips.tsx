import React from 'react';
import { Box, Button } from '@mui/material';

type SuggestionChipsProps = {
  suggestions: string[];
  disabled?: boolean;
  onSelect: (prompt: string) => void;
};

export const SuggestionChips: React.FC<SuggestionChipsProps> = ({
  suggestions,
  disabled = false,
  onSelect,
}) => (
  <Box
    sx={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: 0.8,
      mt: 1.1,
    }}
  >
    {suggestions.map((suggestion) => (
      <Button
        key={suggestion}
        size="small"
        variant="outlined"
        disabled={disabled}
        onClick={() => onSelect(suggestion)}
        sx={{
          textTransform: 'none',
          borderRadius: 999,
          px: 1.2,
          py: 0.45,
          fontSize: '0.78rem',
          fontWeight: 600,
        }}
      >
        {suggestion}
      </Button>
    ))}
  </Box>
);
