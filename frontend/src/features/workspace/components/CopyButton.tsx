import React, { useState } from 'react';
import { Button, IconButton, Tooltip } from '@mui/material';
import { Copy, CopyCheck } from 'lucide-react';
import { useSnackbar } from '@/components/AppLayout';

type CopyButtonProps = {
  text: string;
  label?: string;
  iconOnly?: boolean;
  tooltipLabel?: string;
};

export const CopyButton: React.FC<CopyButtonProps> = ({
  text,
  label = 'Copy to Clipboard',
  iconOnly = false,
  tooltipLabel,
}) => {
  const [copied, setCopied] = useState(false);
  const { showSnackbar } = useSnackbar();

  const handleCopy = async () => {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      showSnackbar('Copied to clipboard.', 'success');
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
      showSnackbar('Failed to copy. Please try again.', 'error');
    }
  };

  const effectiveLabel = copied ? 'Copied' : (tooltipLabel || label);
  const isDisabled = !text.trim();

  if (iconOnly) {
    return (
      <Tooltip title={effectiveLabel} arrow>
        <span>
          <IconButton
            size="small"
            onClick={() => {
              void handleCopy();
            }}
            disabled={isDisabled}
            aria-label={effectiveLabel}
            sx={{
              width: 36,
              height: 36,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 999,
            }}
          >
            {copied ? <CopyCheck size={16} /> : <Copy size={16} />}
          </IconButton>
        </span>
      </Tooltip>
    );
  }

  return (
    <Button
      variant="outlined"
      size="small"
      startIcon={copied ? <CopyCheck size={14} /> : <Copy size={14} />}
      onClick={() => {
        void handleCopy();
      }}
      disabled={isDisabled}
      sx={{
        textTransform: 'none',
        fontWeight: 700,
        borderRadius: 999,
        px: 1.6,
        height: 36,
      }}
    >
      {copied ? 'Copied' : label}
    </Button>
  );
};
