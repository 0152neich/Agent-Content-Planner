import React, { useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Drawer,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Tabs,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import { ExternalLink, History, Rocket, RotateCcw } from 'lucide-react';
import {
  IconAlertTriangle,
  IconCertificate,
  IconDatabaseOff,
  IconFlame,
  IconMessage2,
  IconMicrophone2,
  IconUsers,
} from '@tabler/icons-react';
import { useSnackbar } from '@/components/AppLayout';
import type {
  CampaignResult,
  ContentPlanData,
  ContentSocialPost,
  FacebookPageOption,
  RunItem,
  SocialPublishPlatform,
  SocialPublishResult,
} from '../types';
import {
  buildSnapshotDiff,
  extractContentPlanFromRun,
  getRunLastUpdatedAt,
} from '../historyUtils';
import { buildSocialPostText, normalizeHashtags, normalizeSocialText } from '../socialTextUtils';
import { CopyButton } from './CopyButton';
import { ResultTabsShell } from './ResultTabsShell';
import { SocialCardFacebook } from './SocialCardFacebook';
import { SocialCardLinkedIn } from './SocialCardLinkedIn';

type ResultWorkspacePanelProps = {
  campaignResult: CampaignResult | null;
  loading: boolean;
  activeTab: number;
  onChangeTab: (tab: number) => void;
  historyRuns: RunItem[];
  historyLoading: boolean;
  historyError: string | null;
  restoringRunId: string | null;
  onRestoreRun: (
    runId: string,
    target: 'full_snapshot' | 'analysis' | 'linkedin' | 'facebook',
  ) => Promise<void>;
  onPublishSocialPost: (
    platform: SocialPublishPlatform,
    content: string,
    pageId?: string,
  ) => Promise<SocialPublishResult>;
  onGetFacebookPages: () => Promise<FacebookPageOption[]>;
  onOpenProfile: () => void;
};

const analysisToMarkdown = (result: CampaignResult): string =>
  [
    '## Core Message',
    result.analysis.core_message,
    '',
    '## Value Proposition',
    result.analysis.value_proposition,
    '',
    '## Reader Intent',
    result.analysis.reader_intent,
    '',
    '## Funnel Stage',
    result.analysis.funnel_stage,
    '',
    '## Target Audience',
    result.analysis.target_audience,
    '',
    '## Audience Pain Points',
    ...(result.analysis.audience_pain_points || []).map((item) => `- ${item}`),
    '',
    '## Audience Desired Outcomes',
    ...(result.analysis.audience_desired_outcomes || []).map((item) => `- ${item}`),
    '',
    '## Tone of Voice',
    result.analysis.tone_of_voice,
    '',
    '## Voice Guidelines',
    ...(result.analysis.voice_guidelines || []).map((item) => `- ${item}`),
    '',
    '## Key Takeaways',
    ...(result.analysis.key_takeaways || []).map((item) => `- ${item}`),
    '',
    '## Supporting Claims',
    ...(result.analysis.supporting_claims || []).flatMap((item, index) => [
      `### Claim ${index + 1}`,
      `- Claim: ${item.claim}`,
      `- Evidence: ${item.evidence_excerpt}`,
      `- Reason: ${item.evidence_reason}`,
      '',
    ]),
    '## Primary CTA',
    result.analysis.primary_cta,
    '',
    '## CTA Reasoning',
    result.analysis.cta_reasoning,
    '',
    '## Risk Flags',
    ...(result.analysis.risk_flags || []).map((item) => `- ${item}`),
    '',
    '## Confidence Score',
    String(result.analysis.confidence_score),
    '',
    '## Missing Information',
    ...(result.analysis.missing_information || []).map((item) => `- ${item}`),
  ].join('\n');

const socialToMarkdown = (post: ContentSocialPost | null): string => {
  if (!post) return '';
  const hashtags = normalizeHashtags(post.hashtags);
  return [
    '## Hook',
    normalizeSocialText(post.hook),
    '',
    '## Body',
    normalizeSocialText(post.body_content),
    '',
    '## Call To Action',
    normalizeSocialText(post.call_to_action),
    '',
    '## Hashtags',
    hashtags.join(' '),
  ].join('\n');
};

const socialToPostPreview = (post: ContentSocialPost | null): string => {
  if (!post) return '';
  return buildSocialPostText(post);
};

const getTabSocialPost = (result: CampaignResult, tab: number): ContentSocialPost | null => {
  if (tab === 1) return result.posts.linkedin;
  return result.posts.facebook;
};

const getSectionLabel = (tab: number): string => {
  if (tab === 0) return 'Analysis';
  if (tab === 1) return 'LinkedIn';
  return 'Facebook';
};

const formatUpdatedLabel = (value: string | null): string => {
  if (!value) return 'Updated N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Updated N/A';
  return `Updated ${date.toLocaleString()}`;
};

const formatRunDate = (run: RunItem): string => {
  const source = getRunLastUpdatedAt(run);
  if (!source) return 'Unknown time';
  const parsed = new Date(source);
  if (Number.isNaN(parsed.getTime())) return 'Unknown time';
  return parsed.toLocaleString();
};

const toActionLabel = (run: RunItem): string => {
  const action = String(run.request_payload?.action || '').toUpperCase();
  const trigger = String(run.request_payload?.trigger || '').toLowerCase();
  if (trigger === 'content_plan') return 'Generated from URL';
  if (trigger === 'restore_snapshot') return 'Restored snapshot';
  if (action === 'FULL_REGENERATE') return 'Regenerated content';
  if (action === 'REANALYZE_ONLY') return 'Re-analyzed';
  if (action === 'REWRITE_STRATEGY_ONLY') return 'Updated strategy';
  if (action === 'REWRITE_LINKEDIN_ONLY') return 'Refined LinkedIn';
  if (action === 'REWRITE_FACEBOOK_ONLY') return 'Refined Facebook';
  if (action === 'GENERAL_QA' || action === 'CLARIFY') return 'Assistant answer';
  return 'Updated content';
};

const buildSnapshotFromCampaignResult = (result: CampaignResult): ContentPlanData => {
  const socialPosts = [result.posts.linkedin, result.posts.facebook].filter(
    (item): item is ContentSocialPost => item !== null,
  );
  return {
    source_url: result.meta.source_url || '',
    analysis: {
      core_message: result.analysis.core_message,
      value_proposition: result.analysis.value_proposition,
      reader_intent: result.analysis.reader_intent,
      funnel_stage: result.analysis.funnel_stage,
      target_audience: result.analysis.target_audience,
      audience_pain_points: [...result.analysis.audience_pain_points],
      audience_desired_outcomes: [...result.analysis.audience_desired_outcomes],
      tone_of_voice: result.analysis.tone_of_voice,
      key_takeaways: [...result.analysis.key_takeaways],
      supporting_claims: result.analysis.supporting_claims.map((item) => ({ ...item })),
      voice_guidelines: [...result.analysis.voice_guidelines],
      primary_cta: result.analysis.primary_cta,
      cta_reasoning: result.analysis.cta_reasoning,
      risk_flags: [...result.analysis.risk_flags],
      confidence_score: result.analysis.confidence_score,
      missing_information: [...result.analysis.missing_information],
    },
    social_posts: socialPosts,
  };
};

const hasRunSectionChange = (run: RunItem, tab: number): boolean => {
  const action = String(run.request_payload?.action || '').toUpperCase();
  const trigger = String(run.request_payload?.trigger || '').toLowerCase();
  const affected = Array.isArray(run.response_payload?.affected_sections)
    ? run.response_payload.affected_sections.map((item) => String(item))
    : [];
  const snapshot = extractContentPlanFromRun(run);
  const snapshotHasAnalysis = Boolean(snapshot?.analysis);
  const snapshotHasLinkedIn = Boolean(
    snapshot?.social_posts.some((post) => post.platform.toLowerCase() === 'linkedin'),
  );
  const snapshotHasFacebook = Boolean(
    snapshot?.social_posts.some((post) => post.platform.toLowerCase() === 'facebook'),
  );

  if (tab === 0) {
    return (
      affected.some((item) => item === 'analysis' || item === 'meta.strategy') ||
      action === 'REANALYZE_ONLY' ||
      action === 'REWRITE_STRATEGY_ONLY' ||
      action === 'FULL_REGENERATE' ||
      trigger === 'content_plan' ||
      (trigger === 'restore_snapshot' && snapshotHasAnalysis)
    );
  }
  if (tab === 1) {
    return (
      affected.some((item) => item === 'social_posts.linkedin') ||
      action === 'REWRITE_LINKEDIN_ONLY' ||
      action === 'FULL_REGENERATE' ||
      (trigger === 'content_plan' && snapshotHasLinkedIn) ||
      (trigger === 'restore_snapshot' && snapshotHasLinkedIn)
    );
  }
  return (
    affected.some((item) => item === 'social_posts.facebook') ||
    action === 'REWRITE_FACEBOOK_ONLY' ||
    action === 'FULL_REGENERATE' ||
    (trigger === 'content_plan' && snapshotHasFacebook) ||
    (trigger === 'restore_snapshot' && snapshotHasFacebook)
  );
};

const hasSnapshotForTab = (snapshot: ContentPlanData | null, tab: number): boolean => {
  if (!snapshot) return false;
  if (tab === 0) return true;
  if (tab === 1) return snapshot.social_posts.some((item) => item.platform.toLowerCase().trim() === 'linkedin');
  return snapshot.social_posts.some((item) => item.platform.toLowerCase().trim() === 'facebook');
};

const CONTENT_BRIEF_DEFAULT_VISIBLE_ITEMS = 2;
const VOICE_GUIDELINE_PREVIEW_LENGTH = 170;

type BriefSectionKey = 'sayWhat' | 'sayWho' | 'sayHow' | 'evidence' | 'risk';
type BriefListKey = 'takeaways' | 'painPoints' | 'outcomes';
type ReliabilityLevel = 'high' | 'medium' | 'low';

const getReliabilityLevel = (confidenceScore: number): ReliabilityLevel => {
  if (confidenceScore >= 0.8) return 'high';
  if (confidenceScore >= 0.65) return 'medium';
  return 'low';
};

const truncateListWithToggle = (
  items: string[],
  expanded: boolean,
  limit = CONTENT_BRIEF_DEFAULT_VISIBLE_ITEMS,
): { visibleItems: string[]; hiddenCount: number; canToggle: boolean } => {
  if (expanded) {
    return { visibleItems: items, hiddenCount: 0, canToggle: items.length > limit };
  }
  return {
    visibleItems: items.slice(0, limit),
    hiddenCount: Math.max(0, items.length - limit),
    canToggle: items.length > limit,
  };
};

const buildPublishReadinessItems = (riskFlags: string[], missingInformation: string[]): string[] => {
  const items: string[] = [];
  if (missingInformation.length) {
    items.push(`Bổ sung ${missingInformation.length} thông tin còn thiếu để tránh thiếu ngữ cảnh.`);
  }
  if (riskFlags.length) {
    items.push(`Rà soát ${riskFlags.length} cờ rủi ro để giảm khả năng sai thông điệp.`);
  }
  if (!items.length) {
    items.push('Sẵn sàng publish, chỉ cần kiểm tra lại format và link đính kèm.');
  }
  return items;
};

type ContentBriefDashboardProps = {
  result: CampaignResult;
};

const ContentBriefDashboard: React.FC<ContentBriefDashboardProps> = ({ result }) => {
  const [activeSection, setActiveSection] = useState<BriefSectionKey>('sayWhat');
  const [expandedLists, setExpandedLists] = useState<Record<BriefListKey, boolean>>({
    takeaways: false,
    painPoints: false,
    outcomes: false,
  });
  const [expandedEvidenceByIndex, setExpandedEvidenceByIndex] = useState<Record<number, boolean>>({});
  const [expandedVoiceText, setExpandedVoiceText] = useState(false);

  useEffect(() => {
    setActiveSection('sayWhat');
    setExpandedLists({
      takeaways: false,
      painPoints: false,
      outcomes: false,
    });
    setExpandedEvidenceByIndex({});
    setExpandedVoiceText(false);
  }, [result.meta.run_id]);

  const toggleList = (key: BriefListKey) => {
    setExpandedLists((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const takeawaysView = truncateListWithToggle(result.analysis.key_takeaways, expandedLists.takeaways);
  const painPointsView = truncateListWithToggle(result.analysis.audience_pain_points, expandedLists.painPoints);
  const outcomesView = truncateListWithToggle(
    result.analysis.audience_desired_outcomes,
    expandedLists.outcomes,
  );
  const publishReadinessItems = buildPublishReadinessItems(
    result.analysis.risk_flags,
    result.analysis.missing_information,
  );

  const voiceGuidelineText = result.analysis.voice_guidelines.join(' ').trim();
  const hasMoreVoiceText = voiceGuidelineText.length > VOICE_GUIDELINE_PREVIEW_LENGTH;
  const voicePreview = hasMoreVoiceText
    ? voiceGuidelineText.slice(0, VOICE_GUIDELINE_PREVIEW_LENGTH).trimEnd()
    : voiceGuidelineText;
  const voiceRest = hasMoreVoiceText ? voiceGuidelineText.slice(VOICE_GUIDELINE_PREVIEW_LENGTH) : '';

  const sectionItems: Array<{
    key: BriefSectionKey;
    label: string;
    icon: React.ReactNode;
    iconBg: string;
    danger?: boolean;
  }> = [
    {
      key: 'sayWhat',
      label: 'What',
      icon: <IconMessage2 size={18} />,
      iconBg: 'var(--semantic-pastel-green)',
    },
    {
      key: 'sayWho',
      label: 'Who',
      icon: <IconUsers size={18} />,
      iconBg: 'var(--semantic-pastel-purple)',
    },
    {
      key: 'sayHow',
      label: 'How',
      icon: <IconMicrophone2 size={18} />,
      iconBg: 'var(--semantic-pastel-teal)',
    },
    {
      key: 'evidence',
      label: 'reference',
      icon: <IconCertificate size={18} />,
      iconBg: 'var(--semantic-pastel-blue)',
    },
    {
      key: 'risk',
      label: 'risk',
      icon: <IconAlertTriangle size={18} />,
      iconBg: 'var(--semantic-pastel-red)',
      danger: true,
    },
  ];

  const activeSectionItem =
    sectionItems.find((item) => item.key === activeSection) ?? sectionItems[0];

  const sectionLabelSx = {
    fontSize: '10px',
    textTransform: 'uppercase',
    color: '#6f87a8',
    letterSpacing: '0.02em',
  };

  const sectionDividerSx = {
    borderBottom: '1px solid #bdd0e8',
    py: 0.7,
  };

  const renderActiveSection = (): React.ReactNode => {
    if (activeSection === 'sayWhat') {
      return (
        <Stack spacing={0} sx={{ px: 1.2, py: 0.9 }}>
          <Box sx={sectionDividerSx}>
            <Typography sx={sectionLabelSx}>
              Thông điệp cốt lõi
            </Typography>
            <Typography sx={{ mt: 0.45, fontSize: '1.1rem', fontWeight: 700, color: '#0f2e55' }}>
              {result.analysis.core_message || '-'}
            </Typography>
          </Box>
          <Box sx={sectionDividerSx}>
            <Typography sx={sectionLabelSx}>
              Lợi thế nổi bật
            </Typography>
            <Typography sx={{ mt: 0.45, fontSize: '0.95rem', color: '#315d8b', lineHeight: 1.5 }}>
              {result.analysis.value_proposition || '-'}
            </Typography>
          </Box>
          <Box sx={{ py: 0.7 }}>
            <Typography sx={sectionLabelSx}>
              3 điểm quan trọng nhất
            </Typography>
            <Stack spacing={0.6} sx={{ mt: 0.65 }}>
              {takeawaysView.visibleItems.map((item, index) => (
                <Box
                  key={`${item}-${index}`}
                  sx={{
                    px: 0.9,
                    py: 0.64,
                    borderRadius: 2.5,
                    bgcolor: '#eef1f7',
                  }}
                >
                  <Typography sx={{ fontSize: '0.93rem', color: '#0f2e55' }}>
                    {index + 1}.
                    {' '}{item}
                  </Typography>
                </Box>
              ))}
            </Stack>
            {takeawaysView.canToggle ? (
              <Button
                size="small"
                onClick={() => toggleList('takeaways')}
                sx={{ mt: 0.7, px: 0, color: '#4b3cc8', fontSize: '0.93rem', fontWeight: 600 }}
              >
                {expandedLists.takeaways ? '− Thu gọn' : `+ Xem thêm (${takeawaysView.hiddenCount})`}
              </Button>
            ) : null}
          </Box>
        </Stack>
      );
    }

    if (activeSection === 'sayWho') {
      return (
        <Stack spacing={0.75} sx={{ px: 1.2, py: 0.9 }}>
          <Box sx={sectionDividerSx}>
            <Typography sx={sectionLabelSx}>
              Đối tượng mục tiêu
            </Typography>
            <Stack direction="row" spacing={0.65} flexWrap="wrap" sx={{ mt: 0.55 }}>
              <Chip size="small" label={result.analysis.target_audience || 'General audience'} />
              <Chip size="small" label={`Intent: ${result.analysis.reader_intent}`} />
              <Chip size="small" label={`Funnel: ${result.analysis.funnel_stage}`} />
            </Stack>
            <Typography sx={{ mt: 0.65, fontSize: '0.95rem', color: '#315d8b' }}>
              {result.analysis.target_audience || 'Chưa có mô tả đối tượng.'}
            </Typography>
          </Box>

          <Box sx={sectionDividerSx}>
            <Typography sx={sectionLabelSx}>
              Nỗi đau hàng đầu
            </Typography>
            <Stack spacing={0.5} sx={{ mt: 0.45 }}>
              {painPointsView.visibleItems.map((item, index) => (
                <Box
                  key={`${item}-${index}`}
                  sx={{ px: 0.8, py: 0.6, borderRadius: 2.5, bgcolor: '#eef1f7' }}
                >
                  <Typography sx={{ fontSize: '0.93rem', color: '#0f2e55' }}>
                    {index + 1}.
                    {' '}{item}
                  </Typography>
                </Box>
              ))}
            </Stack>
            {painPointsView.canToggle ? (
              <Button
                size="small"
                onClick={() => toggleList('painPoints')}
                sx={{ mt: 0.55, px: 0, color: '#4b3cc8', fontSize: '0.93rem', fontWeight: 600 }}
              >
                {expandedLists.painPoints ? '− Thu gọn' : `+ Xem thêm (${painPointsView.hiddenCount})`}
              </Button>
            ) : null}
          </Box>

          <Box sx={{ py: 0.7 }}>
            <Typography sx={sectionLabelSx}>
              Kết quả mong muốn
            </Typography>
            <Stack spacing={0.5} sx={{ mt: 0.45 }}>
              {outcomesView.visibleItems.map((item, index) => (
                <Box
                  key={`${item}-${index}`}
                  sx={{ px: 0.8, py: 0.6, borderRadius: 2.5, bgcolor: '#eef1f7' }}
                >
                  <Typography sx={{ fontSize: '0.93rem', color: '#0f2e55' }}>
                    {index + 1}.
                    {' '}{item}
                  </Typography>
                </Box>
              ))}
            </Stack>
            {outcomesView.canToggle ? (
              <Button
                size="small"
                onClick={() => toggleList('outcomes')}
                sx={{ mt: 0.55, px: 0, color: '#4b3cc8', fontSize: '0.93rem', fontWeight: 600 }}
              >
                {expandedLists.outcomes ? '− Thu gọn' : `+ Xem thêm (${outcomesView.hiddenCount})`}
              </Button>
            ) : null}
          </Box>
        </Stack>
      );
    }

    if (activeSection === 'sayHow') {
      return (
        <Stack spacing={0.8} sx={{ px: 1.2, py: 0.9 }}>
          <Box sx={sectionDividerSx}>
            <Typography sx={sectionLabelSx}>
              Giọng điệu
            </Typography>
            <Typography sx={{ mt: 0.45, fontSize: '1.1rem', fontWeight: 700, color: '#0f2e55' }}>
              {result.analysis.tone_of_voice || 'Informative'}
            </Typography>
          </Box>
          <Box sx={{ py: 0.7 }}>
            <Typography sx={sectionLabelSx}>
              Hướng dẫn giọng nói
            </Typography>
            <Typography sx={{ mt: 0.45, fontSize: '0.95rem', color: '#315d8b', lineHeight: 1.55 }}>
              {voicePreview}
              {hasMoreVoiceText && !expandedVoiceText ? '...' : ''}
              {hasMoreVoiceText ? (
                <span style={{ display: expandedVoiceText ? 'inline' : 'none' }}>{voiceRest}</span>
              ) : null}
              {hasMoreVoiceText ? (
                <Box
                  component="button"
                  type="button"
                  onClick={() => setExpandedVoiceText((prev) => !prev)}
                  sx={{
                    ml: 0.6,
                    p: 0,
                    border: 'none',
                    bgcolor: 'transparent',
                    color: '#4b3cc8',
                    cursor: 'pointer',
                    fontSize: '0.93rem',
                  }}
                >
                  {expandedVoiceText ? 'Thu gọn' : 'Xem thêm'}
                </Box>
              ) : null}
            </Typography>
          </Box>
        </Stack>
      );
    }

    if (activeSection === 'evidence') {
      return (
        <Box
          sx={{
            px: 1.2,
            py: 0.9,
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
            gap: 1,
          }}
        >
          {result.analysis.supporting_claims.map((claim, index) => {
            const expanded = Boolean(expandedEvidenceByIndex[index]);
            return (
              <Box
                key={`${claim.claim}-${index}`}
                sx={{
                  border: '1px solid #c1d3e9',
                  borderLeft: '2px solid var(--semantic-evidence-accent)',
                  borderRadius: 1.2,
                  px: 0.85,
                  py: 0.7,
                }}
              >
                <Typography sx={{ fontSize: '0.93rem', fontWeight: 700, color: '#0f2e55' }}>{claim.claim}</Typography>
                <Typography sx={{ mt: 0.45, fontSize: '0.85rem', color: '#315d8b' }}>
                  {claim.evidence_excerpt}
                </Typography>
                {expanded ? (
                  <Typography sx={{ mt: 0.5, fontSize: '0.85rem', color: '#0f2e55' }}>
                    {claim.evidence_reason}
                  </Typography>
                ) : null}
                <Button
                  size="small"
                  onClick={() => {
                    setExpandedEvidenceByIndex((prev) => ({ ...prev, [index]: !expanded }));
                  }}
                  sx={{ mt: 0.4, px: 0, color: '#4b3cc8', fontSize: '0.85rem', fontWeight: 600 }}
                >
                  {expanded ? '▴ Thu gọn' : '▾ Xem thêm'}
                </Button>
              </Box>
            );
          })}
        </Box>
      );
    }

    return (
      <Stack spacing={0.8} sx={{ px: 1.2, py: 0.9 }}>
        <Box sx={{ px: 0.8, py: 0.7, borderRadius: 1.4, border: '0.5px solid var(--semantic-risk-border)', bgcolor: 'var(--semantic-risk-bg)' }}>
          <Stack direction="row" alignItems="center" spacing={0.55}>
            <IconFlame size={14} color="var(--semantic-risk-text)" />
            <Typography sx={{ fontSize: '0.93rem', fontWeight: 700, color: 'var(--semantic-risk-text)' }}>
              Cờ rủi ro
            </Typography>
          </Stack>
          <Stack spacing={0.35} sx={{ mt: 0.45 }}>
            {(result.analysis.risk_flags.length ? result.analysis.risk_flags : ['Không có rủi ro chính']).map((item, index) => (
              <Typography key={`${item}-${index}`} sx={{ fontSize: '0.85rem', color: 'var(--semantic-risk-text)' }}>
                ✕ {item}
              </Typography>
            ))}
          </Stack>
        </Box>

        <Box sx={{ px: 0.8, py: 0.7, borderRadius: 1.4, border: '0.5px solid var(--semantic-missing-border)', bgcolor: 'var(--semantic-missing-bg)' }}>
          <Stack direction="row" alignItems="center" spacing={0.55}>
            <IconDatabaseOff size={14} color="var(--semantic-missing-text)" />
            <Typography sx={{ fontSize: '0.93rem', fontWeight: 700, color: 'var(--semantic-missing-text)' }}>
              Thông tin còn thiếu
            </Typography>
          </Stack>
          <Stack spacing={0.35} sx={{ mt: 0.45 }}>
            {(result.analysis.missing_information.length ? result.analysis.missing_information : ['Không có dữ liệu thiếu nghiêm trọng']).map((item, index) => (
              <Typography key={`${item}-${index}`} sx={{ fontSize: '0.85rem', color: 'var(--semantic-missing-text)' }}>
                ● {item}
              </Typography>
            ))}
          </Stack>
        </Box>

        <Box sx={{ px: 0.8, py: 0.7, borderLeft: '2px solid var(--semantic-accent-main)', bgcolor: 'var(--semantic-brief-pill-bg)' }}>
          <Typography sx={{ fontSize: '0.93rem', fontWeight: 700, color: '#0f2e55' }}>
            Cần bổ sung trước khi publish
          </Typography>
          <Stack spacing={0.35} sx={{ mt: 0.4 }}>
            {publishReadinessItems.map((item, index) => (
              <Typography key={`${item}-${index}`} sx={{ fontSize: '0.85rem', color: '#315d8b' }}>
                → {item}
              </Typography>
            ))}
          </Stack>
        </Box>
      </Stack>
    );
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Box
        sx={{
          px: 0.2,
          py: 0.25,
        }}
      >
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: '1fr',
            gap: 1.2,
            alignItems: 'flex-start',
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: '1.12rem', fontWeight: 700, color: '#1d3148', lineHeight: 1.45 }}>
              {result.analysis.core_message || 'Chưa có thông điệp chính.'}
            </Typography>
            <Chip
              size="small"
              label={result.analysis.value_proposition || result.analysis.target_audience || 'General audience'}
              sx={{
                mt: 0.7,
                height: 32,
                borderRadius: 999,
                bgcolor: '#e8edf4',
                color: '#50709b',
                '& .MuiChip-label': { fontSize: '0.92rem', px: 1 },
              }}
            />
            <Stack direction="row" spacing={0.7} flexWrap="wrap" sx={{ mt: 0.7, rowGap: 0.65 }}>
              <Chip
                size="small"
                label={result.analysis.primary_cta || 'No CTA'}
                sx={{
                  bgcolor: '#e5efd8',
                  color: '#47712e',
                  '& .MuiChip-label': { fontSize: '0.92rem', px: 1 },
                }}
              />
              <Chip
                size="small"
                label={`Mục tiêu: ${result.analysis.reader_intent}`}
                sx={{ '& .MuiChip-label': { fontSize: '0.92rem', px: 1 } }}
              />
              <Chip
                size="small"
                label={`Giai đoạn: ${result.analysis.funnel_stage}`}
                sx={{ '& .MuiChip-label': { fontSize: '0.92rem', px: 1 } }}
              />
            </Stack>
          </Box>

        </Box>
      </Box>

      <Box
        sx={{
          mt: 0.9,
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1fr) 74px' },
          gap: 1,
          alignItems: 'start',
        }}
      >
        <Box sx={{ border: '1px solid #bcd0ea', borderRadius: 1.2, overflow: 'hidden' }}>
          <Box
            sx={{
              px: 1.1,
              py: 0.78,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              borderBottom: '1px solid #bcd0ea',
              borderLeft: activeSectionItem.danger ? '3px solid var(--semantic-risk-text)' : 'none',
              bgcolor: activeSectionItem.danger ? '#fff6f5' : '#f3f4f6',
            }}
          >
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: 999,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                bgcolor: activeSectionItem.iconBg,
                color: 'var(--semantic-text-primary)',
              }}
            >
              {activeSectionItem.icon}
            </Box>
            <Typography sx={{ fontSize: '1rem', fontWeight: 700, color: '#18375b' }}>
              {activeSectionItem.label}
            </Typography>
          </Box>
          {renderActiveSection()}
        </Box>

        <Box
          sx={{
            order: { xs: -1, md: 0 },
            alignSelf: 'start',
            borderRadius: 1.2,
            border: '1px solid #bcd0ea',
            bgcolor: '#f8fafc',
            py: { xs: 0.7, md: 0.8 },
            px: { xs: 0.7, md: 0.52 },
            display: 'flex',
            flexDirection: { xs: 'row', md: 'column' },
            alignItems: 'center',
            justifyContent: 'center',
            gap: 0.65,
          }}
        >
          {sectionItems.map((section) => {
            const isActive = section.key === activeSection;
            return (
              <Tooltip key={section.key} title={section.label} placement="left" arrow>
                <IconButton
                  size="small"
                  onClick={() => setActiveSection(section.key)}
                  sx={{
                    width: 44,
                    height: 44,
                    borderRadius: 1.1,
                    border: '1px solid',
                    borderColor: isActive
                      ? section.danger
                        ? '#d3505b'
                        : '#5850d5'
                      : '#bdd0e7',
                    bgcolor: isActive
                      ? section.danger
                        ? '#fff3f2'
                        : '#eef0ff'
                      : '#f8fafc',
                    color: isActive
                      ? section.danger
                        ? '#d3505b'
                        : '#5850d5'
                      : '#5f7ca0',
                    '&:hover': {
                      bgcolor: section.danger ? '#fff3f2' : '#eef0ff',
                    },
                  }}
                >
                  {section.icon}
                </IconButton>
              </Tooltip>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
};

const renderSocialPanel = (
  post: ContentSocialPost | null,
  tab: number,
): React.ReactNode => {
  const postPreview = socialToPostPreview(post);

  if (!post) {
    return (
      <Typography color="text.secondary">
        No generated post yet for this channel. Ask the refinement assistant to generate one.
      </Typography>
    );
  }

  if (tab === 1) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <SocialCardLinkedIn content={postPreview} />
      </Box>
    );
  }

  if (tab === 2) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <SocialCardFacebook content={postPreview} />
      </Box>
    );
  }
  return null;
};

const panelFieldSx = (changed: boolean) => ({
  borderRadius: 1.5,
  border: '1px solid',
  borderColor: changed ? 'rgba(251,146,60,0.45)' : 'divider',
  bgcolor: changed ? 'rgba(251,146,60,0.08)' : 'transparent',
  p: 1.1,
});

const renderSnapshotByTab = (
  activeTab: number,
  selectedHistorySnapshot: ContentPlanData | null,
): React.ReactNode => {
  if (!selectedHistorySnapshot) {
    return (
      <Typography color="text.secondary">
        This version does not include a content snapshot.
      </Typography>
    );
  }

  if (activeTab === 0) {
    return (
      <Stack spacing={1.1}>
        <Typography sx={{ fontWeight: 700 }}>Analysis Snapshot</Typography>
        <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Core Message</Typography>
          <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.core_message || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Value Proposition</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.value_proposition || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Intent / Funnel</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.reader_intent} / {selectedHistorySnapshot.analysis.funnel_stage}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Target Audience</Typography>
          <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.target_audience || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Pain Points</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.audience_pain_points.join('\n') || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Desired Outcomes</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.audience_desired_outcomes.join('\n') || '-'}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Tone Of Voice</Typography>
          <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.tone_of_voice || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Voice Guidelines</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.voice_guidelines.join('\n') || '-'}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Key Takeaways</Typography>
          <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.key_takeaways.join('\n') || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Primary CTA</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.primary_cta || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>CTA Reasoning</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.cta_reasoning || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Risk Flags</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.risk_flags.join('\n') || '-'}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Confidence</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.confidence_score.toFixed(2)}
          </Typography>
          <Typography sx={{ mt: 0.7, fontWeight: 700, fontSize: '0.82rem' }}>Missing Information</Typography>
          <Typography sx={{ mt: 0.35, whiteSpace: 'pre-wrap' }}>
            {selectedHistorySnapshot.analysis.missing_information.join('\n') || '-'}
          </Typography>
        </Paper>
      </Stack>
    );
  }

  const platform = activeTab === 1 ? 'linkedin' : 'facebook';
  const aliases = [platform];
  const post =
    selectedHistorySnapshot.social_posts.find((item) =>
      aliases.includes(item.platform.toLowerCase().trim()),
    ) || null;

  if (!post) {
    return (
      <Typography color="text.secondary">
        This version has no {platform} post snapshot.
      </Typography>
    );
  }

  return (
    <Stack spacing={1.1}>
      <Typography sx={{ fontWeight: 700 }}>{platform.toUpperCase()} Snapshot</Typography>
      <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Hook</Typography>
        <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>{post.hook || '-'}</Typography>
      </Paper>
      <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Body</Typography>
        <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>{post.body_content || '-'}</Typography>
      </Paper>
      <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Call To Action</Typography>
        <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>{post.call_to_action || '-'}</Typography>
      </Paper>
      <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.6 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Hashtags</Typography>
        <Typography sx={{ mt: 0.4, whiteSpace: 'pre-wrap' }}>
          {normalizeHashtags(post.hashtags).join(' ') || '-'}
        </Typography>
      </Paper>
    </Stack>
  );
};

const renderDiffByTab = (
  activeTab: number,
  snapshotDiff: ReturnType<typeof buildSnapshotDiff>,
): React.ReactNode => {
  if (activeTab === 0) {
    return (
      <Stack spacing={1.1}>
        <Typography sx={{ fontWeight: 700 }}>
          {snapshotDiff.hasChanges ? 'Detected changes' : 'No differences detected'}
        </Typography>
        <Box sx={panelFieldSx(snapshotDiff.analysis.core_message.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Core Message</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.core_message.before || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.core_message.after || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.value_proposition.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Value Proposition</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.value_proposition.before || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.value_proposition.after || '-'}</Typography>
        </Box>
        <Box
          sx={panelFieldSx(
            snapshotDiff.analysis.reader_intent.changed || snapshotDiff.analysis.funnel_stage.changed,
          )}
        >
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Intent / Funnel</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>
            {snapshotDiff.analysis.reader_intent.before || '-'} / {snapshotDiff.analysis.funnel_stage.before || '-'}
          </Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>
            {snapshotDiff.analysis.reader_intent.after || '-'} / {snapshotDiff.analysis.funnel_stage.after || '-'}
          </Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.target_audience.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Target Audience</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.target_audience.before || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.target_audience.after || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.audience_pain_points.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Audience Pain Points</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.audience_pain_points.before.join('\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.audience_pain_points.after.join('\n') || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.audience_desired_outcomes.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Audience Desired Outcomes</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.audience_desired_outcomes.before.join('\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.audience_desired_outcomes.after.join('\n') || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.tone_of_voice.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Tone Of Voice</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.tone_of_voice.before || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.tone_of_voice.after || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.voice_guidelines.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Voice Guidelines</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.voice_guidelines.before.join('\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.voice_guidelines.after.join('\n') || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.key_takeaways.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Key Takeaways</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.key_takeaways.before.join('\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.key_takeaways.after.join('\n') || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.supporting_claims.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Supporting Claims</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.supporting_claims.before.join('\n\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.supporting_claims.after.join('\n\n') || '-'}</Typography>
        </Box>
        <Box
          sx={panelFieldSx(
            snapshotDiff.analysis.primary_cta.changed || snapshotDiff.analysis.cta_reasoning.changed,
          )}
        >
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>CTA Guidance</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current CTA</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.primary_cta.before || '-'}</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current Reasoning</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.cta_reasoning.before || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected CTA</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.primary_cta.after || '-'}</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Selected Reasoning</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.cta_reasoning.after || '-'}</Typography>
        </Box>
        <Box sx={panelFieldSx(snapshotDiff.analysis.risk_flags.changed)}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Risk Flags</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.risk_flags.before.join('\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.risk_flags.after.join('\n') || '-'}</Typography>
        </Box>
        <Box
          sx={panelFieldSx(
            snapshotDiff.analysis.confidence_score.changed || snapshotDiff.analysis.missing_information.changed,
          )}
        >
          <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Reliability</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current confidence</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.confidence_score.before.toFixed(2)}</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current missing info</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.missing_information.before.join('\n') || '-'}</Typography>
          <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected confidence</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.confidence_score.after.toFixed(2)}</Typography>
          <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Selected missing info</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{snapshotDiff.analysis.missing_information.after.join('\n') || '-'}</Typography>
        </Box>
      </Stack>
    );
  }

  const platform = activeTab === 1 ? 'linkedin' : 'facebook';
  const diff = snapshotDiff.social[platform];
  if (!diff) {
    return <Typography color="text.secondary">No diff data for {platform} in this version.</Typography>;
  }
  const changed =
    diff.hook.changed || diff.body_content.changed || diff.call_to_action.changed || diff.hashtags.changed;

  return (
    <Stack spacing={1.1}>
      <Typography sx={{ fontWeight: 700 }}>
        {changed ? 'Detected changes' : 'No differences detected'}
      </Typography>
      <Box sx={panelFieldSx(diff.hook.changed)}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Hook</Typography>
        <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{diff.hook.before || '-'}</Typography>
        <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{diff.hook.after || '-'}</Typography>
      </Box>
      <Box sx={panelFieldSx(diff.body_content.changed)}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Body</Typography>
        <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{diff.body_content.before || '-'}</Typography>
        <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{diff.body_content.after || '-'}</Typography>
      </Box>
      <Box sx={panelFieldSx(diff.call_to_action.changed)}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Call To Action</Typography>
        <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{diff.call_to_action.before || '-'}</Typography>
        <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>{diff.call_to_action.after || '-'}</Typography>
      </Box>
      <Box sx={panelFieldSx(diff.hashtags.changed)}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem' }}>Hashtags</Typography>
        <Typography sx={{ mt: 0.35, fontSize: '0.78rem', color: 'text.secondary' }}>Current</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>
          {normalizeHashtags(diff.hashtags.before).join(' ') || '-'}
        </Typography>
        <Typography sx={{ mt: 0.6, fontSize: '0.78rem', color: 'text.secondary' }}>Selected version</Typography>
        <Typography sx={{ whiteSpace: 'pre-wrap' }}>
          {normalizeHashtags(diff.hashtags.after).join(' ') || '-'}
        </Typography>
      </Box>
    </Stack>
  );
};

export const ResultWorkspacePanel: React.FC<ResultWorkspacePanelProps> = ({
  campaignResult,
  loading,
  activeTab,
  onChangeTab,
  historyRuns,
  historyLoading,
  historyError,
  restoringRunId,
  onRestoreRun,
  onPublishSocialPost,
  onGetFacebookPages,
  onOpenProfile,
}) => {
  const { showSnackbar } = useSnackbar();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedHistoryRunId, setSelectedHistoryRunId] = useState<string | null>(null);
  const [historyDetailOpen, setHistoryDetailOpen] = useState(false);
  const [historyTab, setHistoryTab] = useState(0);
  const [publishingState, setPublishingState] = useState<
    Record<SocialPublishPlatform, boolean>
  >({
    linkedin: false,
    facebook: false,
  });
  const [publishedPosts, setPublishedPosts] = useState<
    Partial<Record<SocialPublishPlatform, SocialPublishResult>>
  >({});
  const [showConnectSocialCta, setShowConnectSocialCta] = useState<SocialPublishPlatform | null>(null);
  const [facebookPages, setFacebookPages] = useState<FacebookPageOption[]>([]);
  const [facebookPagesLoading, setFacebookPagesLoading] = useState(false);
  const [facebookPageDialogOpen, setFacebookPageDialogOpen] = useState(false);
  const [selectedFacebookPageId, setSelectedFacebookPageId] = useState('');

  const socialPost = useMemo(
    () => (campaignResult ? getTabSocialPost(campaignResult, activeTab) : null),
    [campaignResult, activeTab],
  );

  const markdown = useMemo(() => {
    if (!campaignResult) return '';
    if (activeTab === 0) return analysisToMarkdown(campaignResult);
    if (socialPost) return socialToMarkdown(socialPost);
    if (activeTab === 1) return campaignResult.linkedin;
    return campaignResult.facebook;
  }, [campaignResult, activeTab, socialPost]);

  const publishPlatform: SocialPublishPlatform | null =
    activeTab === 1 ? 'linkedin' : activeTab === 2 ? 'facebook' : null;
  const publishContent = useMemo(
    () => (socialPost ? socialToPostPreview(socialPost) : ''),
    [socialPost],
  );
  const publishDisabled = publishPlatform
    ? publishingState[publishPlatform] ||
      (!publishedPosts[publishPlatform] && !publishContent.trim())
    : true;
  const publishTooltipLabel = publishPlatform
    ? publishedPosts[publishPlatform]
      ? 'View Post'
      : publishingState[publishPlatform]
        ? 'Publishing...'
        : publishPlatform === 'facebook'
          ? 'Publish to Facebook'
          : 'Publish to LinkedIn'
    : '';
  const analysisReliability = campaignResult
    ? (() => {
        const level = getReliabilityLevel(campaignResult.analysis.confidence_score);
        const confidencePercent = Math.round(campaignResult.analysis.confidence_score * 100);
        if (level === 'high') {
          return { text: 'Cao', color: '#47712e', bg: '#e5efd8', border: '#47712e', percent: confidencePercent };
        }
        if (level === 'medium') {
          return {
            text: 'Trung bình',
            color: '#9a6700',
            bg: '#fdf4d7',
            border: '#d0a84b',
            percent: confidencePercent,
          };
        }
        return { text: 'Thấp', color: '#b42318', bg: '#ffeceb', border: '#fda29b', percent: confidencePercent };
      })()
    : null;

  useEffect(() => {
    setPublishedPosts({});
    setShowConnectSocialCta(null);
  }, [campaignResult?.meta.run_id]);

  const relevantHistoryRuns = useMemo(
    () => historyRuns.filter((run) => hasRunSectionChange(run, activeTab)),
    [historyRuns, activeTab],
  );

  const selectedHistoryRun = useMemo(() => {
    if (!relevantHistoryRuns.length || !selectedHistoryRunId) return null;
    return relevantHistoryRuns.find((run) => run.id === selectedHistoryRunId) ?? null;
  }, [relevantHistoryRuns, selectedHistoryRunId]);

  const selectedHistorySnapshot = useMemo(
    () => (selectedHistoryRun ? extractContentPlanFromRun(selectedHistoryRun) : null),
    [selectedHistoryRun],
  );

  const currentSnapshot = useMemo(
    () => (campaignResult ? buildSnapshotFromCampaignResult(campaignResult) : null),
    [campaignResult],
  );

  const snapshotDiff = useMemo(
    () => buildSnapshotDiff(currentSnapshot, selectedHistorySnapshot),
    [currentSnapshot, selectedHistorySnapshot],
  );

  const openHistoryPanel = () => {
    setHistoryOpen(true);
  };

  useEffect(() => {
    if (!selectedHistoryRunId) return;
    const stillAvailable = relevantHistoryRuns.some((run) => run.id === selectedHistoryRunId);
    if (!stillAvailable) {
      setSelectedHistoryRunId(null);
    }
  }, [relevantHistoryRuns, selectedHistoryRunId]);

  const runHasSnapshot = selectedHistorySnapshot !== null;
  const runHasSnapshotForCurrentTab = hasSnapshotForTab(selectedHistorySnapshot, activeTab);
  const restoreTarget: 'full_snapshot' | 'analysis' | 'linkedin' | 'facebook' =
    activeTab === 0 ? 'analysis' : activeTab === 1 ? 'linkedin' : 'facebook';

  const publishWithOptionalPage = async (platform: SocialPublishPlatform, pageId?: string) => {
    setPublishingState((prev) => ({ ...prev, [platform]: true }));
    try {
      const result = await onPublishSocialPost(platform, publishContent, pageId);
      setPublishedPosts((prev) => ({ ...prev, [platform]: result }));
      showSnackbar('Successfully published!', 'success');
      setShowConnectSocialCta(null);
      if (platform === 'facebook') {
        setFacebookPageDialogOpen(false);
      }
    } catch (error) {
      const errorCode =
        error &&
        typeof error === 'object' &&
        'code' in error &&
        typeof (error as { code?: unknown }).code === 'string'
          ? (error as { code: string }).code
          : null;
      const message = error instanceof Error ? error.message : 'Failed to publish post.';
      if (errorCode === 'SOCIAL_NOT_CONNECTED') {
        setShowConnectSocialCta(platform);
      }
      showSnackbar(message, 'error');
    } finally {
      setPublishingState((prev) => ({ ...prev, [platform]: false }));
    }
  };

  const handlePublishAction = async () => {
    if (!publishPlatform) {
      return;
    }

    const existingPublished = publishedPosts[publishPlatform];
    if (existingPublished?.view_url) {
      window.open(existingPublished.view_url, '_blank', 'noopener,noreferrer');
      return;
    }

    if (!publishContent.trim()) {
      showSnackbar('No generated content to publish yet.', 'warning');
      return;
    }

    if (publishPlatform === 'facebook') {
      setFacebookPageDialogOpen(true);
      setFacebookPagesLoading(true);
      try {
        const pages = await onGetFacebookPages();
        setFacebookPages(pages);
        if (pages.length === 1) {
          setSelectedFacebookPageId(pages[0].id);
        } else if (!pages.some((item) => item.id === selectedFacebookPageId)) {
          setSelectedFacebookPageId('');
        }
      } catch (error) {
        const errorCode =
          error &&
          typeof error === 'object' &&
          'code' in error &&
          typeof (error as { code?: unknown }).code === 'string'
            ? (error as { code: string }).code
            : null;
        const message = error instanceof Error ? error.message : 'Failed to load Facebook pages.';
        if (errorCode === 'SOCIAL_NOT_CONNECTED') {
          setShowConnectSocialCta('facebook');
        }
        showSnackbar(message, 'error');
        setFacebookPageDialogOpen(false);
      } finally {
        setFacebookPagesLoading(false);
      }
      return;
    }
    await publishWithOptionalPage(publishPlatform);
  };

  return (
    <Box
      id="campaign-result-panel"
      sx={{
        height: '100%',
        minHeight: 0,
        display: 'flex',
        flexDirection: 'column',
        bgcolor: isDark ? '#0f1115' : '#ffffff',
      }}
    >
      <Box
        sx={{
          px: 2.1,
          py: 0.9,
          borderBottom: '1px solid',
          borderColor: isDark ? 'rgba(255,255,255,0.1)' : '#E5E7EB',
          position: 'sticky',
          top: 0,
          zIndex: 3,
          bgcolor: isDark ? 'rgba(15,17,21,0.84)' : 'rgba(255,255,255,0.84)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 1.5,
          overflow: 'hidden',
          '&::after': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: '-35%',
            width: '35%',
            height: '100%',
            pointerEvents: 'none',
            background: isDark
              ? 'linear-gradient(120deg, rgba(0,0,0,0), rgba(75,145,255,0.18), rgba(0,0,0,0))'
              : 'linear-gradient(120deg, rgba(255,255,255,0), rgba(129,185,255,0.34), rgba(255,255,255,0))',
            animation: 'workspaceShimmer 4.4s ease-in-out infinite',
            '@media (prefers-reduced-motion: reduce)': {
              animation: 'none',
            },
          },
          '@keyframes workspaceShimmer': {
            '0%': { transform: 'translateX(0%)' },
            '100%': { transform: 'translateX(420%)' },
          },
        }}
      >
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <ResultTabsShell activeTab={activeTab} onChangeTab={onChangeTab} />
        </Box>
      </Box>

      <Box sx={{ flex: 1, minHeight: 0, overflowY: 'auto', px: { xs: 1.4, md: 2.6 }, py: 2 }}>
        {loading ? (
          <Box
            sx={{
              minHeight: 220,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 1,
            }}
          >
            <CircularProgress size={18} />
            <Typography color="text.secondary">Loading campaign output...</Typography>
          </Box>
        ) : !campaignResult ? (
          <Box
            sx={{
              minHeight: 220,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              textAlign: 'center',
            }}
          >
            <Typography color="text.secondary">
              No generated output yet. Ask the refinement assistant to generate content.
            </Typography>
          </Box>
        ) : (
          <Box sx={{ p: { xs: 0.4, md: 0.8 } }}>
            <Box
              sx={{
                mb: 1.5,
                display: 'flex',
                alignItems: { xs: 'flex-start', md: 'center' },
                justifyContent: 'space-between',
                gap: 1.2,
                flexWrap: 'wrap',
              }}
            >
              <Stack spacing={0.5} alignItems="flex-start">
                <Stack direction="row" gap={0.75} flexWrap="wrap" alignItems="center">
                  <Chip
                    size="small"
                    label={campaignResult.meta.selected_model || 'Unknown model'}
                    sx={{
                      borderRadius: 999,
                      height: 28,
                      fontWeight: 700,
                      bgcolor: isDark ? 'rgba(59,130,246,0.18)' : '#e7f1ff',
                      color: isDark ? '#bfdbfe' : '#1d4e89',
                    }}
                  />
                  <Chip
                    size="small"
                    label={formatUpdatedLabel(campaignResult.meta.updated_at)}
                    sx={{
                      borderRadius: 999,
                      height: 28,
                      bgcolor: isDark ? 'rgba(148,163,184,0.16)' : '#eef2f7',
                      color: isDark ? '#cbd5e1' : '#334155',
                    }}
                  />
                </Stack>
                {activeTab === 0 && analysisReliability ? (
                  <Chip
                    size="small"
                    label={`Độ tin cậy ${analysisReliability.text} (${analysisReliability.percent}%)`}
                    sx={{
                      height: 24,
                      borderRadius: 1.1,
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      color: analysisReliability.color,
                      bgcolor: analysisReliability.bg,
                      border: '1px solid',
                      borderColor: analysisReliability.border,
                    }}
                  />
                ) : null}
              </Stack>
              <Stack
                direction="row"
                spacing={0.8}
                alignItems="center"
                sx={{
                  ml: 'auto',
                  flexWrap: 'nowrap',
                  overflowX: { xs: 'auto', md: 'visible' },
                  maxWidth: '100%',
                  pb: { xs: 0.2, md: 0 },
                }}
              >
                <Tooltip title="History" arrow>
                  <span>
                    <IconButton
                      size="small"
                      onClick={openHistoryPanel}
                      disabled={historyLoading}
                      aria-label="History"
                      sx={{
                        width: 36,
                        height: 36,
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 999,
                      }}
                    >
                      {historyLoading ? <CircularProgress size={16} /> : <History size={16} />}
                    </IconButton>
                  </span>
                </Tooltip>
                <CopyButton
                  text={markdown}
                  iconOnly
                  tooltipLabel={activeTab === 0 ? 'Copy Analysis' : 'Copy Post'}
                />
                {publishPlatform ? (
                  <Tooltip title={publishTooltipLabel} arrow>
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => {
                          void handlePublishAction();
                        }}
                        disabled={publishDisabled}
                        aria-label={publishTooltipLabel}
                        sx={{
                          width: 36,
                          height: 36,
                          borderRadius: 999,
                          color: '#ffffff',
                          background: 'linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)',
                          '&:hover': {
                            background: 'linear-gradient(135deg, #0284c7 0%, #1d4ed8 100%)',
                          },
                          '&.Mui-disabled': {
                            background: isDark ? 'rgba(100,116,139,0.35)' : 'rgba(148,163,184,0.6)',
                            color: '#ffffff',
                          },
                        }}
                      >
                        {publishingState[publishPlatform] ? (
                          <CircularProgress size={16} color="inherit" />
                        ) : publishedPosts[publishPlatform] ? (
                          <ExternalLink size={16} />
                        ) : (
                          <Rocket size={16} />
                        )}
                      </IconButton>
                    </span>
                  </Tooltip>
                ) : null}
              </Stack>
            </Box>

            {showConnectSocialCta ? (
              <Paper
                variant="outlined"
                sx={{
                  mb: 1.2,
                  p: 1,
                  borderRadius: 1.5,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  borderColor: isDark ? 'rgba(96,165,250,0.4)' : '#bfdbfe',
                  bgcolor: isDark ? 'rgba(30,64,175,0.18)' : '#eff6ff',
                }}
              >
                <Typography
                  sx={{ fontSize: '0.86rem', color: isDark ? '#dbeafe' : '#1d4e89' }}
                >
                  {showConnectSocialCta === 'facebook'
                    ? 'Facebook account is not connected. Connect your account to publish.'
                    : 'LinkedIn account is not connected. Connect your account to publish.'}
                </Typography>
                <Button
                  size="small"
                  variant="contained"
                  onClick={() => {
                    onOpenProfile();
                  }}
                >
                  Connect
                </Button>
              </Paper>
            ) : null}

            {activeTab === 0 ? <ContentBriefDashboard result={campaignResult} /> : renderSocialPanel(socialPost, activeTab)}
          </Box>
        )}
      </Box>

      <Drawer
        anchor={isMobile ? 'bottom' : 'right'}
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        PaperProps={{
          sx: {
            width: isMobile ? '100%' : 520,
            maxHeight: isMobile ? '86vh' : '100vh',
            borderTopLeftRadius: isMobile ? 16 : 0,
            borderTopRightRadius: isMobile ? 16 : 0,
          },
        }}
      >
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.4, height: '100%' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography sx={{ fontWeight: 700, fontSize: '1rem' }}>
              {getSectionLabel(activeTab)} History
            </Typography>
            {historyLoading ? <CircularProgress size={16} /> : null}
          </Box>

          {historyError ? (
            <Typography color="error.main" sx={{ fontSize: '0.86rem' }}>
              {historyError}
            </Typography>
          ) : null}

          <Box sx={{ maxHeight: 280, overflowY: 'auto', pr: 0.3 }}>
            {!relevantHistoryRuns.length ? (
              <Typography sx={{ p: 1.5, color: 'text.secondary', fontSize: '0.88rem' }}>
                No version history for {getSectionLabel(activeTab)} yet.
              </Typography>
            ) : (
              <Stack spacing={0.9}>
                {relevantHistoryRuns.map((run, index) => {
                const isSelected = selectedHistoryRun?.id === run.id;
                const isCurrent = campaignResult?.meta.run_id === run.id;
                return (
                  <Box
                    key={run.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      setSelectedHistoryRunId(run.id);
                      setHistoryTab(0);
                      setHistoryDetailOpen(true);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        setSelectedHistoryRunId(run.id);
                        setHistoryTab(0);
                        setHistoryDetailOpen(true);
                      }
                    }}
                    sx={{
                      p: 1.3,
                      borderRadius: 2.2,
                      border: '1px solid',
                      borderColor: isSelected
                        ? (isDark ? 'rgba(96,165,250,0.7)' : '#93c5fd')
                        : (isDark ? 'rgba(148,163,184,0.35)' : '#d4deea'),
                      bgcolor: isSelected
                        ? (isDark ? 'rgba(59,130,246,0.18)' : '#e8f0ff')
                        : (isDark ? 'rgba(255,255,255,0.03)' : '#edf2fb'),
                      cursor: 'pointer',
                      transition: 'all 0.18s ease',
                      '&:hover': {
                        borderColor: isDark ? 'rgba(96,165,250,0.7)' : '#93c5fd',
                      },
                    }}
                  >
                    <Stack direction="row" spacing={0.6} alignItems="center" flexWrap="wrap">
                      <Typography sx={{ fontSize: '1.05rem', fontWeight: 800 }}>
                        Version {relevantHistoryRuns.length - index}
                      </Typography>
                      {isCurrent ? (
                        <Chip
                          size="small"
                          label="Current"
                          sx={{
                            bgcolor: isDark ? 'rgba(59,130,246,0.22)' : '#2196f3',
                            color: isDark ? '#93c5fd' : '#ffffff',
                            fontWeight: 700,
                            borderRadius: 999,
                          }}
                        />
                      ) : null}
                      <Chip
                        size="small"
                        label={run.status}
                        variant="outlined"
                        sx={{
                          textTransform: 'lowercase',
                          borderRadius: 999,
                          color: isDark ? 'rgba(203,213,225,0.95)' : '#4a6b91',
                          borderColor: isDark ? 'rgba(203,213,225,0.35)' : '#9db8db',
                        }}
                      />
                    </Stack>
                    <Typography sx={{ mt: 0.55, fontSize: '0.95rem', color: 'text.secondary' }}>
                      {formatRunDate(run)}
                    </Typography>
                    <Typography sx={{ mt: 0.25, fontSize: '0.98rem', color: 'text.secondary' }}>
                      {toActionLabel(run)} • {String(run.request_payload?.selected_model || campaignResult?.meta.selected_model || 'unknown')}
                    </Typography>
                  </Box>
                );
              })}
              </Stack>
            )}
          </Box>
        </Box>
      </Drawer>

      <Dialog
        open={facebookPageDialogOpen}
        onClose={() => setFacebookPageDialogOpen(false)}
        fullWidth
        maxWidth="xs"
      >
        <DialogTitle>Select Facebook Page</DialogTitle>
        <DialogContent>
          {facebookPagesLoading ? (
            <Box sx={{ py: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
              <CircularProgress size={16} />
              <Typography color="text.secondary">Loading pages...</Typography>
            </Box>
          ) : facebookPages.length === 0 ? (
            <Typography color="text.secondary">
              No Facebook pages available. Ensure your Facebook connection has page permissions.
            </Typography>
          ) : (
            <FormControl fullWidth sx={{ mt: 1 }}>
              <InputLabel id="facebook-page-label">Page</InputLabel>
              <Select
                labelId="facebook-page-label"
                label="Page"
                value={selectedFacebookPageId}
                onChange={(event) => setSelectedFacebookPageId(String(event.target.value))}
              >
                {facebookPages.map((page) => (
                  <MenuItem key={page.id} value={page.id}>
                    {page.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFacebookPageDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            disabled={
              facebookPagesLoading ||
              !selectedFacebookPageId ||
              publishingState.facebook
            }
            onClick={() => {
              void publishWithOptionalPage('facebook', selectedFacebookPageId);
            }}
          >
            {publishingState.facebook ? 'Publishing...' : 'Publish'}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={historyDetailOpen && Boolean(selectedHistoryRun)}
        onClose={() => setHistoryDetailOpen(false)}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle sx={{ pb: 1 }}>
          {selectedHistoryRun
            ? `Version details · ${formatRunDate(selectedHistoryRun)}`
            : 'Version details'}
        </DialogTitle>
        <DialogContent dividers sx={{ pt: 1.2 }}>
          <Tabs value={historyTab} onChange={(_e, value) => setHistoryTab(value)} sx={{ minHeight: 36 }}>
            <Tab label="Snapshot" sx={{ textTransform: 'none', minHeight: 36 }} />
            <Tab label="Diff" sx={{ textTransform: 'none', minHeight: 36 }} />
          </Tabs>
          <Box sx={{ mt: 1.2, maxHeight: '56vh', overflowY: 'auto' }}>
            {!selectedHistoryRun ? (
              <Typography color="text.secondary">No version selected.</Typography>
            ) : historyTab === 0 ? (
              renderSnapshotByTab(activeTab, selectedHistorySnapshot)
            ) : (
              renderDiffByTab(activeTab, snapshotDiff)
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 1.5 }}>
          <Button onClick={() => setHistoryDetailOpen(false)}>Close</Button>
          <Button
            variant="contained"
            startIcon={<RotateCcw size={16} />}
            disabled={!selectedHistoryRun || !runHasSnapshot || !runHasSnapshotForCurrentTab || restoringRunId !== null}
            onClick={() => {
              if (selectedHistoryRun) {
                void onRestoreRun(selectedHistoryRun.id, restoreTarget).then(() => {
                  setHistoryDetailOpen(false);
                  setHistoryOpen(false);
                });
              }
            }}
          >
            {restoringRunId && selectedHistoryRun?.id === restoringRunId
              ? 'Restoring...'
              : `Restore ${getSectionLabel(activeTab)}`}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
