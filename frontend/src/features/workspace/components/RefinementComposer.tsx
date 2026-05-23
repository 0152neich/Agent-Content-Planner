import React, { useCallback } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Select,
  TextField,
  Tooltip,
} from '@mui/material';
import { Send, X } from 'lucide-react';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';

type ModelOption = {
  value: string;
  label: string;
};

type RefinementComposerProps = {
  value: string;
  selectedModel: string;
  modelOptions: ModelOption[];
  disabled?: boolean;
  refining?: boolean;
  onChangeValue: (value: string) => void;
  onSelectModel: (value: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
};

export const RefinementComposer: React.FC<RefinementComposerProps> = ({
  value,
  selectedModel,
  modelOptions,
  disabled = false,
  refining = false,
  onChangeValue,
  onSelectModel,
  onSubmit,
  onCancel,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const isDark = theme.palette.mode === 'dark';

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        onSubmit();
      }
    },
    [onSubmit],
  );
  const selectedModelLabel =
    modelOptions.find((option) => option.value === selectedModel)?.label || selectedModel;

  return (
    <Box
      sx={{
        mt: 0.4,
        border: '1px solid',
        borderColor: isDark ? 'rgba(255,255,255,0.14)' : '#CAD7E6',
        bgcolor: isDark ? '#0e1318' : '#ffffff',
        borderRadius: 1.4,
        p: 0.7,
      }}
    >
      <TextField
        value={value}
        disabled={disabled}
        onChange={(event) => onChangeValue(event.target.value)}
        onKeyDown={handleKeyDown}
        multiline
        minRows={1}
        maxRows={4}
        fullWidth
        variant="standard"
        placeholder={t('workspacePage.refinement.placeholder')}
        InputProps={{ disableUnderline: true }}
        sx={{
          '& .MuiInputBase-root': {
            fontSize: '0.88rem',
            lineHeight: 1.35,
            color: isDark ? '#eff4fb' : 'inherit',
          },
        }}
      />

      <Box sx={{ mt: 0.75, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.7 }}>
        {/** Keep model picker compact to avoid taking over composer width. */}
        <Tooltip title={selectedModelLabel} placement="top">
          <Select
            value={selectedModel}
            onChange={(event) => onSelectModel(String(event.target.value))}
            size="small"
            disabled={disabled}
            renderValue={(value) => {
              const found = modelOptions.find((option) => option.value === value);
              return found?.label ?? String(value);
            }}
            MenuProps={{
              PaperProps: {
                sx: {
                  minWidth: 250,
                  maxHeight: 330,
                },
              },
            }}
            sx={{
              width: 154,
              minWidth: 154,
              borderRadius: 1.4,
              '& .MuiOutlinedInput-root': {
                height: 32,
                borderRadius: 1.4,
                display: 'flex',
                alignItems: 'center',
                backgroundColor: 'transparent',
                boxShadow: 'none',
                transition:
                  'background-color 0.2s ease, outline-color 0.2s ease, box-shadow 0.2s ease',
                '& .MuiOutlinedInput-notchedOutline': {
                  border: 'none',
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  border: 'none',
                },
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  border: 'none',
                },
                '&:hover': {
                  backgroundColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(15,123,220,0.08)',
                  outline: isDark ? '1px solid rgba(255,255,255,0.2)' : '1px solid rgba(15,123,220,0.3)',
                },
                '&.Mui-focused': {
                  backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(15,123,220,0.1)',
                  outline: isDark ? '1px solid rgba(0,163,255,0.6)' : '1px solid rgba(15,123,220,0.55)',
                  boxShadow: isDark
                    ? '0 0 0 3px rgba(0,163,255,0.2)'
                    : '0 0 0 3px rgba(15,123,220,0.16)',
                },
              },
              '& .MuiSelect-select': {
                minHeight: '32px !important',
                py: 0,
                pl: 1,
                pr: 3.5,
                fontSize: '0.78rem',
                fontWeight: 600,
                lineHeight: 1.1,
                display: 'flex',
                alignItems: 'center',
                boxSizing: 'border-box',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              },
              '& .MuiSelect-icon': {
                right: 8,
                top: '50%',
                transform: 'translateY(-50%)',
              },
            }}
          >
            {modelOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </Tooltip>
        {refining ? (
          <Button
            variant="outlined"
            color="inherit"
            onClick={onCancel}
            aria-label={t('workspacePage.refinement.cancelAria')}
            sx={{
              minWidth: 34,
              width: 34,
              height: 34,
              px: 0,
              borderRadius: 1.4,
            }}
          >
            <Box sx={{ position: 'relative', width: 14, height: 14, display: 'inline-flex' }}>
              <CircularProgress size={14} color="inherit" sx={{ position: 'absolute', inset: 0 }} />
              <X size={10} style={{ position: 'absolute', inset: 2 }} />
            </Box>
          </Button>
        ) : (
          <Button
            variant="contained"
            disabled={disabled || !value.trim()}
            onClick={onSubmit}
            sx={{
              minWidth: 34,
              width: 34,
              height: 34,
              px: 0,
              borderRadius: 1.4,
            }}
          >
            <Send size={14} />
          </Button>
        )}
      </Box>
    </Box>
  );
};
