export type ProjectItem = {
  id: string;
  owner_user_id: string;
  name: string;
  source_url: string | null;
  description: string | null;
  status: string;
  last_active_at: string | null;
  createdAt: string | null;
  updatedAt: string | null;
};

export type ConversationItem = {
  id: string;
  project_id: string;
  title: string;
  selected_model: string | null;
  status: string;
  message_count: number;
  last_message_at: string | null;
  createdAt: string | null;
  updatedAt: string | null;
};

export type MessageItem = {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  error: string | null;
  createdAt: string | null;
};

export type RunItem = {
  id: string;
  conversation_id: string;
  project_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  source_url: string | null;
  platforms: string[];
  request_payload: {
    trigger?: string;
    action?: string;
    selected_model?: string;
    restored_from_run_id?: string;
    [key: string]: unknown;
  };
  response_payload: Record<string, unknown>;
  createdAt: string | null;
};

export type ChatIntentItem = {
  action: string;
  target_platform: string | null;
  normalized_prompt: string;
  confidence: number;
  reason: string | null;
};

export type ConversationMessageCreateResult = {
  user_message: MessageItem | null;
  assistant_message: MessageItem | null;
  run: RunItem;
  intent?: ChatIntentItem | null;
  affected_sections?: string[];
  content_plan_snapshot?: Record<string, unknown> | null;
};

export type ContentAnalysis = {
  core_message: string;
  value_proposition: string;
  reader_intent: 'learn' | 'evaluate' | 'act';
  funnel_stage: 'awareness' | 'consideration' | 'decision';
  audience_pain_points: string[];
  audience_desired_outcomes: string[];
  key_takeaways: string[];
  supporting_claims: Array<{
    claim: string;
    evidence_excerpt: string;
    evidence_reason: string;
  }>;
  target_audience: string;
  tone_of_voice: string;
  voice_guidelines: string[];
  primary_cta: string;
  cta_reasoning: string;
  risk_flags: string[];
  confidence_score: number;
  missing_information: string[];
};

export type ContentSocialPost = {
  platform: string;
  hook: string;
  body_content: string;
  call_to_action: string;
  hashtags: string[];
};

export type ContentPlanData = {
  source_url: string;
  analysis: ContentAnalysis;
  social_posts: ContentSocialPost[];
};

export type CampaignResult = {
  analysis: ContentAnalysis;
  linkedin: string;
  facebook: string;
  posts: {
    linkedin: ContentSocialPost | null;
    facebook: ContentSocialPost | null;
  };
  meta: {
    source_url: string;
    run_id: string | null;
    selected_model: string | null;
    updated_at: string | null;
  };
};

export type WorkspaceChatMessage = {
  id: string;
  role: 'system' | 'user' | 'assistant';
  content: string;
  isLoading?: boolean;
  createdAt?: string | null;
};

export type SocialPublishPlatform = 'linkedin' | 'facebook';

export type SocialPublishResult = {
  platform: SocialPublishPlatform;
  provider_post_id: string;
  view_url: string;
};

export type FacebookPageOption = {
  id: string;
  name: string;
  tasks: string[];
  perms: string[];
};

export type AutopostJobStatus =
  | 'QUEUED'
  | 'GENERATING'
  | 'READY'
  | 'SCHEDULED'
  | 'PUBLISHED'
  | 'FAILED'
  | 'NEEDS_RECONNECT'
  | 'CANCELLED';

export type AutopostPlatform = 'linkedin' | 'facebook';

export type AutopostJobItem = {
  id: string;
  project_id: string;
  user_id: string;
  platform: AutopostPlatform;
  keyword: string;
  timezone: string;
  scheduled_at: string;
  status: AutopostJobStatus;
  page_id: string | null;
  draft_content: string | null;
  final_content: string | null;
  provider_post_id: string | null;
  provider_schedule_id: string | null;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  conversation_run_id: string | null;
  createdAt: string | null;
  updatedAt: string | null;
};
