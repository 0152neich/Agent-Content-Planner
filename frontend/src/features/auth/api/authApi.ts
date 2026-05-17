import { clearAccessToken, getAccessToken, setAccessToken } from '../authStorage';
import {
  API_BASE_URL,
  requestEnvelope,
  requestEnvelopeNullable,
  withAuthHeaders,
} from '@/lib/apiClient';
import type { UserItem } from '@/features/users/api/userApi';

export type LoginPayload = {
  identifier: string;
  password: string;
};

export type RegisterPayload = {
  user_name: string;
  email: string;
  password: string;
  full_name?: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  is_active?: boolean;
  email_verified?: boolean;
  role?: string;
};

export type AuthTokenResult = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserItem;
};

export type ForgotPasswordSendOtpResult = {
  sent: boolean;
  expires_in: number;
  message: string;
};

export type ForgotPasswordVerifyOtpResult = {
  verified: boolean;
  reset_token: string;
  expires_in: number;
};

export type ForgotPasswordResetResult = {
  reset: boolean;
};

let refreshInFlight: Promise<string | null> | null = null;

export const loginApi = async (payload: LoginPayload): Promise<AuthTokenResult> =>
  requestEnvelope<AuthTokenResult>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const refreshApi = async (): Promise<AuthTokenResult> =>
  requestEnvelope<AuthTokenResult>('/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  });

export const logoutApi = async (): Promise<{ logged_out: boolean }> =>
  requestEnvelope<{ logged_out: boolean }>('/auth/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
  });

export const meApi = async (accessToken: string): Promise<UserItem> =>
  requestEnvelope<UserItem>('/auth/me', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const registerApi = async (payload: RegisterPayload): Promise<UserItem> =>
  requestEnvelope<UserItem>('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_name: payload.user_name,
      email: payload.email,
      password: payload.password,
      full_name: payload.full_name ?? null,
      phone: payload.phone ?? null,
      avatar_url: payload.avatar_url ?? null,
      is_active: payload.is_active ?? true,
      email_verified: payload.email_verified ?? false,
      role: payload.role ?? 'user',
    }),
  });

export const forgotPasswordSendOtpApi = async (email: string): Promise<ForgotPasswordSendOtpResult> =>
  requestEnvelope<ForgotPasswordSendOtpResult>('/auth/forgot-password/send-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

export const forgotPasswordVerifyOtpApi = async (
  email: string,
  otp: string,
): Promise<ForgotPasswordVerifyOtpResult> =>
  requestEnvelope<ForgotPasswordVerifyOtpResult>('/auth/forgot-password/verify-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp }),
  });

export const forgotPasswordResetApi = async (
  resetToken: string,
  newPassword: string,
): Promise<ForgotPasswordResetResult> =>
  requestEnvelope<ForgotPasswordResetResult>('/auth/forgot-password/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reset_token: resetToken, new_password: newPassword }),
  });

export const startGoogleLogin = (): void => {
  window.location.href = `${API_BASE_URL}/auth/google/login`;
};

export const ensureAuthenticatedAccessToken = async (): Promise<string | null> => {
  const currentToken = getAccessToken();
  if (currentToken) {
    const meResult = await requestEnvelopeNullable<UserItem>('/auth/me', {
      headers: withAuthHeaders(currentToken),
      credentials: 'include',
    });
    if (meResult.success && meResult.data) {
      return currentToken;
    }
  }

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const refreshResult = await requestEnvelopeNullable<AuthTokenResult>('/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      if (!refreshResult.success || !refreshResult.data) {
        clearAccessToken();
        return null;
      }

      setAccessToken(refreshResult.data.access_token);
      return refreshResult.data.access_token;
    })();
  }

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
};
