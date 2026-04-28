import type { ContentPlanData, ContentSocialPost, RunItem } from './types';

const toText = (value: unknown): string => (typeof value === 'string' ? value : '');

const toStringArray = (value: unknown): string[] =>
  Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];

const normalizeList = (values: string[]): string[] =>
  values.map((item) => item.trim()).filter(Boolean);

const toReaderIntent = (value: unknown): 'learn' | 'evaluate' | 'act' => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'evaluate') return 'evaluate';
  if (normalized === 'act') return 'act';
  return 'learn';
};

const toFunnelStage = (
  value: unknown,
): 'awareness' | 'consideration' | 'decision' => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'consideration') return 'consideration';
  if (normalized === 'decision') return 'decision';
  return 'awareness';
};

const toConfidence = (value: unknown): number => {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return 0.6;
  if (parsed < 0) return 0;
  if (parsed > 1) return 1;
  return parsed;
};

const toSupportingClaims = (
  value: unknown,
): Array<{ claim: string; evidence_excerpt: string; evidence_reason: string }> => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const source = item as Record<string, unknown>;
      return {
        claim: toText(source.claim),
        evidence_excerpt: toText(source.evidence_excerpt),
        evidence_reason: toText(source.evidence_reason),
      };
    })
    .filter(
      (item) =>
        item.claim.trim().length > 0 &&
        item.evidence_excerpt.trim().length > 0 &&
        item.evidence_reason.trim().length > 0,
    );
};

const findPostByPlatform = (
  posts: ContentSocialPost[],
  aliases: string[],
): ContentSocialPost | null => {
  const lowerAliases = aliases.map((item) => item.toLowerCase());
  return (
    posts.find((post) => lowerAliases.includes(post.platform.toLowerCase().trim())) ?? null
  );
};

const ensureAtLeast = (items: string[], minSize: number, fallback: string): string[] => {
  const next = [...items];
  if (!next.length) {
    next.push(fallback);
  }
  while (next.length < minSize) {
    next.push(next[next.length - 1]);
  }
  return next;
};

export const parseContentPlanSnapshot = (value: unknown): ContentPlanData | null => {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const source = value as Record<string, unknown>;
  const analysisRaw = source.analysis;
  const postsRaw = source.social_posts;
  if (!analysisRaw || typeof analysisRaw !== 'object' || !Array.isArray(postsRaw)) {
    return null;
  }
  const analysisSource = analysisRaw as Record<string, unknown>;
  const socialPosts = postsRaw
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const post = item as Record<string, unknown>;
      return {
        platform: toText(post.platform),
        hook: toText(post.hook),
        body_content: toText(post.body_content),
        call_to_action: toText(post.call_to_action),
        hashtags: toStringArray(post.hashtags),
      };
    })
    .filter((item) => item.platform.length > 0);

  const keyTakeaways = ensureAtLeast(
    normalizeList(toStringArray(analysisSource.key_takeaways)).slice(0, 5),
    3,
    'No key takeaway extracted from source.',
  );
  const painPoints = ensureAtLeast(
    normalizeList(toStringArray(analysisSource.audience_pain_points)).slice(0, 5),
    3,
    'Key pain point not clearly stated in source.',
  );
  const desiredOutcomes = ensureAtLeast(
    normalizeList(toStringArray(analysisSource.audience_desired_outcomes)).slice(0, 5),
    3,
    'Desired outcome not clearly stated in source.',
  );
  const voiceGuidelines = ensureAtLeast(
    normalizeList(toStringArray(analysisSource.voice_guidelines)).slice(0, 5),
    3,
    'Keep language clear and audience-specific.',
  );
  const riskFlags = ensureAtLeast(
    normalizeList(toStringArray(analysisSource.risk_flags)).slice(0, 4),
    2,
    'Limited evidence depth in source article.',
  ).slice(0, 4);
  const missingInformation = normalizeList(
    toStringArray(analysisSource.missing_information),
  );

  const supportingClaims = toSupportingClaims(analysisSource.supporting_claims);
  const normalizedSupportingClaims =
    supportingClaims.length >= 3
      ? supportingClaims.slice(0, 5)
      : keyTakeaways.slice(0, 3).map((item) => ({
        claim: item,
        evidence_excerpt: item,
        evidence_reason: 'Derived from available source summary context.',
        }));

  return {
    source_url: toText(source.source_url),
    analysis: {
      core_message:
        toText(analysisSource.core_message) || 'No core message extracted.',
      value_proposition:
        toText(analysisSource.value_proposition) ||
        'No explicit value proposition identified.',
      reader_intent: toReaderIntent(analysisSource.reader_intent),
      funnel_stage: toFunnelStage(analysisSource.funnel_stage),
      target_audience:
        toText(analysisSource.target_audience) || 'General audience',
      audience_pain_points: painPoints,
      audience_desired_outcomes: desiredOutcomes,
      key_takeaways: keyTakeaways,
      supporting_claims: normalizedSupportingClaims,
      tone_of_voice:
        toText(analysisSource.tone_of_voice) || 'Informative',
      voice_guidelines: voiceGuidelines,
      primary_cta:
        toText(analysisSource.primary_cta) || 'Take one concrete next action.',
      cta_reasoning:
        toText(analysisSource.cta_reasoning) ||
        'CTA aligns with inferred reader intent.',
      risk_flags: riskFlags,
      confidence_score: toConfidence(analysisSource.confidence_score),
      missing_information: missingInformation.length
        ? missingInformation
        : ['No explicit benchmark or quantified evidence found in source.'],
    },
    social_posts: socialPosts,
  };
};

export const extractContentPlanFromRun = (run: RunItem): ContentPlanData | null => {
  const snapshot = run.response_payload?.content_plan_snapshot;
  if (snapshot) {
    const parsed = parseContentPlanSnapshot(snapshot);
    if (parsed) {
      return parsed;
    }
  }
  return parseContentPlanSnapshot(run.response_payload);
};

type DiffField = {
  before: string;
  after: string;
  changed: boolean;
};

type DiffNumberField = {
  before: number;
  after: number;
  changed: boolean;
};

type DiffListField = {
  before: string[];
  after: string[];
  changed: boolean;
};

export type SnapshotDiff = {
  analysis: {
    core_message: DiffField;
    value_proposition: DiffField;
    reader_intent: DiffField;
    funnel_stage: DiffField;
    target_audience: DiffField;
    audience_pain_points: DiffListField;
    audience_desired_outcomes: DiffListField;
    key_takeaways: DiffListField;
    supporting_claims: DiffListField;
    tone_of_voice: DiffField;
    voice_guidelines: DiffListField;
    primary_cta: DiffField;
    cta_reasoning: DiffField;
    risk_flags: DiffListField;
    confidence_score: DiffNumberField;
    missing_information: DiffListField;
  };
  social: Record<
    'linkedin' | 'facebook',
    | null
    | {
        hook: DiffField;
        body_content: DiffField;
        call_to_action: DiffField;
        hashtags: DiffListField;
      }
  >;
  hasChanges: boolean;
};

const createDiffField = (before: string, after: string): DiffField => ({
  before,
  after,
  changed: before !== after,
});

const createDiffNumberField = (before: number, after: number): DiffNumberField => ({
  before,
  after,
  changed: before !== after,
});

const createDiffListField = (before: string[], after: string[]): DiffListField => {
  const normalizedBefore = normalizeList(before);
  const normalizedAfter = normalizeList(after);
  return {
    before: normalizedBefore,
    after: normalizedAfter,
    changed: normalizedBefore.join('\n') !== normalizedAfter.join('\n'),
  };
};

const formatSupportingClaim = (
  claim: { claim: string; evidence_excerpt: string; evidence_reason: string },
): string => {
  return `Claim: ${claim.claim}\nEvidence: ${claim.evidence_excerpt}\nReason: ${claim.evidence_reason}`;
};

const buildPostDiff = (
  before: ContentSocialPost | null,
  after: ContentSocialPost | null,
) => {
  if (!before && !after) {
    return null;
  }
  return {
    hook: createDiffField(before?.hook || '', after?.hook || ''),
    body_content: createDiffField(before?.body_content || '', after?.body_content || ''),
    call_to_action: createDiffField(before?.call_to_action || '', after?.call_to_action || ''),
    hashtags: createDiffListField(before?.hashtags || [], after?.hashtags || []),
  };
};

export const buildSnapshotDiff = (
  baseSnapshot: ContentPlanData | null,
  compareSnapshot: ContentPlanData | null,
): SnapshotDiff => {
  const basePosts = baseSnapshot?.social_posts || [];
  const comparePosts = compareSnapshot?.social_posts || [];

  const analysisDiff = {
    core_message: createDiffField(
      baseSnapshot?.analysis.core_message || '',
      compareSnapshot?.analysis.core_message || '',
    ),
    value_proposition: createDiffField(
      baseSnapshot?.analysis.value_proposition || '',
      compareSnapshot?.analysis.value_proposition || '',
    ),
    reader_intent: createDiffField(
      baseSnapshot?.analysis.reader_intent || '',
      compareSnapshot?.analysis.reader_intent || '',
    ),
    funnel_stage: createDiffField(
      baseSnapshot?.analysis.funnel_stage || '',
      compareSnapshot?.analysis.funnel_stage || '',
    ),
    target_audience: createDiffField(
      baseSnapshot?.analysis.target_audience || '',
      compareSnapshot?.analysis.target_audience || '',
    ),
    audience_pain_points: createDiffListField(
      baseSnapshot?.analysis.audience_pain_points || [],
      compareSnapshot?.analysis.audience_pain_points || [],
    ),
    audience_desired_outcomes: createDiffListField(
      baseSnapshot?.analysis.audience_desired_outcomes || [],
      compareSnapshot?.analysis.audience_desired_outcomes || [],
    ),
    key_takeaways: createDiffListField(
      baseSnapshot?.analysis.key_takeaways || [],
      compareSnapshot?.analysis.key_takeaways || [],
    ),
    supporting_claims: createDiffListField(
      (baseSnapshot?.analysis.supporting_claims || []).map(formatSupportingClaim),
      (compareSnapshot?.analysis.supporting_claims || []).map(formatSupportingClaim),
    ),
    tone_of_voice: createDiffField(
      baseSnapshot?.analysis.tone_of_voice || '',
      compareSnapshot?.analysis.tone_of_voice || '',
    ),
    voice_guidelines: createDiffListField(
      baseSnapshot?.analysis.voice_guidelines || [],
      compareSnapshot?.analysis.voice_guidelines || [],
    ),
    primary_cta: createDiffField(
      baseSnapshot?.analysis.primary_cta || '',
      compareSnapshot?.analysis.primary_cta || '',
    ),
    cta_reasoning: createDiffField(
      baseSnapshot?.analysis.cta_reasoning || '',
      compareSnapshot?.analysis.cta_reasoning || '',
    ),
    risk_flags: createDiffListField(
      baseSnapshot?.analysis.risk_flags || [],
      compareSnapshot?.analysis.risk_flags || [],
    ),
    confidence_score: createDiffNumberField(
      baseSnapshot?.analysis.confidence_score || 0,
      compareSnapshot?.analysis.confidence_score || 0,
    ),
    missing_information: createDiffListField(
      baseSnapshot?.analysis.missing_information || [],
      compareSnapshot?.analysis.missing_information || [],
    ),
  };

  const socialDiff = {
    linkedin: buildPostDiff(
      findPostByPlatform(basePosts, ['linkedin']),
      findPostByPlatform(comparePosts, ['linkedin']),
    ),
    facebook: buildPostDiff(
      findPostByPlatform(basePosts, ['facebook']),
      findPostByPlatform(comparePosts, ['facebook']),
    ),
  };

  const hasAnalysisChanges = Object.values(analysisDiff).some((item) =>
    Boolean((item as { changed?: boolean }).changed),
  );

  const hasSocialChanges = (Object.values(socialDiff) as Array<typeof socialDiff.linkedin>).some(
    (item) =>
      item !== null &&
      (item.hook.changed ||
        item.body_content.changed ||
        item.call_to_action.changed ||
        item.hashtags.changed),
  );

  return {
    analysis: analysisDiff,
    social: socialDiff,
    hasChanges: hasAnalysisChanges || hasSocialChanges,
  };
};
