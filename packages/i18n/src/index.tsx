import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { en, type MessageKey } from './en';
import { hi } from './hi';
import { kn } from './kn';

export type Lang = 'en' | 'kn' | 'hi';
export const LANGS: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
  { code: 'hi', label: 'हिन्दी' },
];
export const catalogues: Record<Lang, Record<MessageKey, string>> = { en, kn, hi };
export type { MessageKey };

const STORAGE_KEY = 'oglos.lang';

export function format(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m));
}

export function translate(lang: Lang, key: MessageKey, params?: Record<string, string | number>) {
  return format(catalogues[lang][key] ?? en[key] ?? key, params);
}

/** Translate an API error code (e.g. INVALID_CODE) with a generic fallback. */
export function errorKey(code: string | undefined): MessageKey {
  const key = `errors.${(code ?? 'generic').toLowerCase()}` as MessageKey;
  return key in en ? key : 'errors.generic';
}

/** Pick the user's language for an i18n map from the API ({en, kn, hi}). */
export function pick(map: Record<string, string> | undefined, lang: Lang): string {
  if (!map) return '';
  return map[lang] || map.en || Object.values(map)[0] || '';
}

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: MessageKey, params?: Record<string, string | number>) => string;
}

const Ctx = createContext<I18n | null>(null);

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'en' || saved === 'kn' || saved === 'hi') return saved;
  } catch {
    /* storage unavailable */
  }
  return 'en';
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* storage unavailable */
    }
  }, []);
  const value = useMemo<I18n>(
    () => ({ lang, setLang, t: (key, params) => translate(lang, key, params) }),
    [lang, setLang],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}
