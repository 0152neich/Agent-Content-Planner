import React from 'react';
import { Box, Link, Typography } from '@mui/material';

const renderInline = (text: string): React.ReactNode[] => {
  const linkRegex = /\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null = linkRegex.exec(text);

  while (match) {
    const [full, label, href] = match;
    const index = match.index;
    if (index > lastIndex) {
      parts.push(text.slice(lastIndex, index));
    }
    parts.push(
      <Link
        key={`${href}-${index}`}
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        underline="hover"
      >
        {label}
      </Link>,
    );
    lastIndex = index + full.length;
    match = linkRegex.exec(text);
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts;
};

const isBulletLine = (line: string): boolean =>
  line.trim().startsWith('- ') || line.trim().startsWith('* ');

const isNumberedLine = (line: string): boolean => /^\d+\.\s+/.test(line.trim());

type MarkdownBlockProps = {
  value: string;
};

export const MarkdownBlock: React.FC<MarkdownBlockProps> = ({ value }) => {
  const lines = value.split('\n');
  const nodes: React.ReactNode[] = [];
  let cursor = 0;

  while (cursor < lines.length) {
    const line = lines[cursor];
    const trimmed = line.trim();

    if (!trimmed) {
      cursor += 1;
      continue;
    }

    if (trimmed.startsWith('### ')) {
      nodes.push(
        <Typography key={`h3-${cursor}`} variant="subtitle1" sx={{ mt: 1.2, mb: 0.6, fontWeight: 700 }}>
          {renderInline(trimmed.slice(4))}
        </Typography>,
      );
      cursor += 1;
      continue;
    }

    if (trimmed.startsWith('## ')) {
      nodes.push(
        <Typography key={`h2-${cursor}`} variant="h6" sx={{ mt: 1.4, mb: 0.7, fontWeight: 700 }}>
          {renderInline(trimmed.slice(3))}
        </Typography>,
      );
      cursor += 1;
      continue;
    }

    if (trimmed.startsWith('# ')) {
      nodes.push(
        <Typography key={`h1-${cursor}`} variant="h5" sx={{ mt: 1.5, mb: 0.8, fontWeight: 800 }}>
          {renderInline(trimmed.slice(2))}
        </Typography>,
      );
      cursor += 1;
      continue;
    }

    if (isBulletLine(trimmed)) {
      const items: string[] = [];
      while (cursor < lines.length && isBulletLine(lines[cursor])) {
        items.push(lines[cursor].trim().slice(2));
        cursor += 1;
      }
      nodes.push(
        <Box key={`ul-${cursor}`} component="ul" sx={{ m: 0, pl: 2.8 }}>
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>
              <Typography variant="body1" sx={{ mb: 0.4 }}>
                {renderInline(item)}
              </Typography>
            </li>
          ))}
        </Box>,
      );
      continue;
    }

    if (isNumberedLine(trimmed)) {
      const items: string[] = [];
      while (cursor < lines.length && isNumberedLine(lines[cursor])) {
        items.push(lines[cursor].trim().replace(/^\d+\.\s+/, ''));
        cursor += 1;
      }
      nodes.push(
        <Box key={`ol-${cursor}`} component="ol" sx={{ m: 0, pl: 3 }}>
          {items.map((item, index) => (
            <li key={`${item}-${index}`}>
              <Typography variant="body1" sx={{ mb: 0.4 }}>
                {renderInline(item)}
              </Typography>
            </li>
          ))}
        </Box>,
      );
      continue;
    }

    const paragraphs: string[] = [trimmed];
    cursor += 1;
    while (
      cursor < lines.length &&
      lines[cursor].trim() &&
      !lines[cursor].trim().startsWith('#') &&
      !isBulletLine(lines[cursor]) &&
      !isNumberedLine(lines[cursor])
    ) {
      paragraphs.push(lines[cursor].trim());
      cursor += 1;
    }

    nodes.push(
      <Typography key={`p-${cursor}`} variant="body1" sx={{ lineHeight: 1.75, mb: 1 }}>
        {renderInline(paragraphs.join(' '))}
      </Typography>,
    );
  }

  return <Box>{nodes}</Box>;
};
