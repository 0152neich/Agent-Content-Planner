const ACCESS_TOKEN_KEY = 'auth-access-token';
const REMEMBERED_IDENTIFIER_KEY = 'auth-remembered-identifier';
const hasStorage = () => typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';

export const setAccessToken = (token: string) => {
  if (!hasStorage()) return;
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
};

export const getAccessToken = (): string | null => {
  if (!hasStorage()) return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

export const clearAccessToken = () => {
  if (!hasStorage()) return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
};

export const setRememberedIdentifier = (identifier: string) => {
  if (!hasStorage()) return;
  localStorage.setItem(REMEMBERED_IDENTIFIER_KEY, identifier);
};

export const getRememberedIdentifier = (): string | null => {
  if (!hasStorage()) return null;
  return localStorage.getItem(REMEMBERED_IDENTIFIER_KEY);
};

export const clearRememberedIdentifier = () => {
  if (!hasStorage()) return;
  localStorage.removeItem(REMEMBERED_IDENTIFIER_KEY);
};
