import { requestEnvelope, withAuthHeaders } from '@/lib/apiClient';

export type FacebookConnectionStatus = {
  connected: boolean;
  provider: 'facebook';
  display_name: string | null;
  account_id: string | null;
  expires_at: string | null;
};

export const getFacebookConnectionApi = async (
  accessToken: string,
): Promise<FacebookConnectionStatus> =>
  requestEnvelope<FacebookConnectionStatus>('/social/facebook/connection', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const startFacebookConnectApi = async (
  accessToken: string,
  returnTo?: string,
): Promise<{ authorize_url: string }> =>
  requestEnvelope<{ authorize_url: string }>(
    `/social/facebook/connect${returnTo ? `?return_to=${encodeURIComponent(returnTo)}` : ''}`,
    {
      method: 'POST',
      headers: withAuthHeaders(accessToken),
      credentials: 'include',
    },
  );

export const disconnectFacebookApi = async (
  accessToken: string,
): Promise<{ disconnected: boolean }> =>
  requestEnvelope<{ disconnected: boolean }>('/social/facebook/connection', {
    method: 'DELETE',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });
