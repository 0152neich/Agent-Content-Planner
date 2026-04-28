import type { ContentSocialPost } from './types';

const stripInlineMarkdown = (value: string): string => {
  return value
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '');
};

export const normalizeSocialText = (value: string): string => {
  return stripInlineMarkdown(value).replace(/\r\n/g, '\n').trim();
};

const normalizeHashtagItem = (value: string): string => {
  const cleaned = value
    .trim()
    .replace(/^#+/, '')
    .replace(/\s+/g, '');
  return cleaned ? `#${cleaned}` : '';
};

export const normalizeHashtags = (hashtags: string[]): string[] => {
  const deduped = new Set<string>();
  for (const item of hashtags) {
    const normalized = normalizeHashtagItem(item);
    if (normalized) {
      deduped.add(normalized);
    }
  }
  return [...deduped];
};

export const buildSocialPostText = (post: ContentSocialPost): string => {
  const sections = [
    normalizeSocialText(post.hook),
    normalizeSocialText(post.body_content),
    normalizeSocialText(post.call_to_action),
  ].filter(Boolean);

  const hashtags = normalizeHashtags(post.hashtags);
  if (hashtags.length) {
    sections.push(hashtags.join(' '));
  }
  return sections.join('\n\n').trim();
};
