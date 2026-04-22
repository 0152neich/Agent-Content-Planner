import { requestEnvelope, withAuthHeaders } from '@/lib/apiClient';

export type LinkedInConnectionStatus = {
  connected: boolean;
  provider: 'linkedin';
  display_name: string | null;
  member_urn: string | null;
  expires_at: string | null;
};

export const getLinkedInConnectionApi = async (
  accessToken: string,
): Promise<LinkedInConnectionStatus> =>
  requestEnvelope<LinkedInConnectionStatus>('/social/linkedin/connection', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const startLinkedInConnectApi = async (
  accessToken: string,
  returnTo?: string,
): Promise<{ authorize_url: string }> =>
  requestEnvelope<{ authorize_url: string }>(
    `/social/linkedin/connect${returnTo ? `?return_to=${encodeURIComponent(returnTo)}` : ''}`,
    {
    method: 'POST',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  },
  );

export const disconnectLinkedInApi = async (
  accessToken: string,
): Promise<{ disconnected: boolean }> =>
  requestEnvelope<{ disconnected: boolean }>('/social/linkedin/connection', {
    method: 'DELETE',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });
