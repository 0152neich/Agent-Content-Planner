import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from './locales/en.json';
import vi from './locales/vi.json';

export const SUPPORTED_LANGUAGES = ['en', 'vi'] as const;
export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number];

export const normalizeSupportedLanguage = (value: string | null | undefined): SupportedLanguage => {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized.startsWith('vi')) return 'vi';
  return 'en';
};

const detectedLanguage = normalizeSupportedLanguage(
  typeof window !== 'undefined' ? localStorage.getItem('i18nextLng') : 'en',
);

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      vi: { translation: vi },
    },
    lng: detectedLanguage,
    fallbackLng: 'en',
    supportedLngs: [...SUPPORTED_LANGUAGES],
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      caches: ['localStorage'],
    },
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
