import { requestEnvelope, withAuthHeaders } from '@/lib/apiClient';

export type UserItem = {
  id: string;
  user_name: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  is_active: boolean;
  email_verified: boolean;
  role: string;
  createdAt: string | null;
  updatedAt: string | null;
};

export type UserCreatePayload = {
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

export type UserUpdatePayload = {
  user_name?: string;
  email?: string;
  password?: string;
  full_name?: string | null;
  phone?: string | null;
  avatar_url?: string | null;
  is_active?: boolean;
  email_verified?: boolean;
  role?: string;
};

export const listUsersApi = async (accessToken: string): Promise<UserItem[]> =>
  requestEnvelope<{ users: UserItem[] }>('/users', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  }).then((data) => data.users);

export const getUserByIdApi = async (accessToken: string, userId: string): Promise<UserItem> =>
  requestEnvelope<UserItem>(`/users/${userId}`, {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const createUserApi = async (payload: UserCreatePayload): Promise<UserItem> =>
  requestEnvelope<UserItem>('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const updateUserApi = async (
  accessToken: string,
  userId: string,
  payload: UserUpdatePayload,
): Promise<UserItem> =>
  requestEnvelope<UserItem>(`/users/${userId}`, {
    method: 'PUT',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
    body: JSON.stringify(payload),
  });

export const uploadUserAvatarApi = async (
  accessToken: string,
  userId: string,
  file: File,
): Promise<UserItem> => {
  const formData = new FormData();
  formData.append('file', file);

  return requestEnvelope<UserItem>(`/users/${userId}/avatar`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    credentials: 'include',
    body: formData,
  });
};

export const deleteUserApi = async (
  accessToken: string,
  userId: string,
): Promise<{ id: string; deleted: boolean }> =>
  requestEnvelope<{ id: string; deleted: boolean }>(`/users/${userId}`, {
    method: 'DELETE',
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });

export const getMyProfileByTokenApi = async (accessToken: string): Promise<UserItem> =>
  requestEnvelope<UserItem>('/auth/me', {
    headers: withAuthHeaders(accessToken),
    credentials: 'include',
  });
