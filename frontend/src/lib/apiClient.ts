export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export type ApiEnvelope<T> = {
  success: boolean;
  data: T | null;
  error: string | null;
};

const NETWORK_ERROR_MESSAGE =
  'Failed to fetch. Please check backend URL, CORS, and network connectivity.';

const parseEnvelope = async <T>(response: Response): Promise<ApiEnvelope<T>> => {
  try {
    return (await response.json()) as ApiEnvelope<T>;
  } catch {
    if (response.status === 504) {
      return {
        success: false,
        data: null,
        error: 'Request timed out while waiting for the server. Please retry.',
      };
    }
    if (!response.ok) {
      return {
        success: false,
        data: null,
        error: `Request failed with status ${response.status}.`,
      };
    }
    return { success: false, data: null, error: 'Invalid response.' };
  }
};

const parseJson = async <T>(response: Response): Promise<T | null> => {
  try {
    return (await response.json()) as T;
  } catch {
    return null;
  }
};

export const withAuthHeaders = (accessToken: string) => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${accessToken}`,
});

export const requestEnvelope = async <T>(
  path: string,
  init?: RequestInit,
): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  const body = await parseEnvelope<T>(response);
  if (!response.ok || !body.success || body.data === null || body.data === undefined) {
    throw new Error(body.error || `Request failed with status ${response.status}.`);
  }
  return body.data;
};

export const requestJson = async <T>(path: string, init?: RequestInit): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new Error(NETWORK_ERROR_MESSAGE);
  }

  const body = await parseJson<T>(response);
  if (!response.ok) {
    if (body && typeof body === 'object' && 'error' in body) {
      throw new Error(String((body as { error?: unknown }).error || 'Request failed.'));
    }
    throw new Error(`Request failed with status ${response.status}.`);
  }
  if (body === null) {
    throw new Error('Invalid response.');
  }
  return body;
};

export const requestEnvelopeNullable = async <T>(
  path: string,
  init?: RequestInit,
): Promise<ApiEnvelope<T>> => {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, init);
    return await parseEnvelope<T>(response);
  } catch {
    return { success: false, data: null, error: NETWORK_ERROR_MESSAGE };
  }
};
