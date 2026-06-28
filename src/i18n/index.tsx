import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import zh, { type TranslationKey } from './zh';
import en from './en';

type Lang = 'zh-CN' | 'en';

const translations: Record<Lang, Record<TranslationKey, string>> = {
  'zh-CN': zh,
  en,
};

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue>({
  lang: 'zh-CN',
  setLang: () => {},
  t: (key) => key,
});

export function I18nProvider({
  initialLang,
  onLangChange,
  children,
}: {
  initialLang: Lang;
  onLangChange?: (lang: Lang) => void;
  children: ReactNode;
}) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  const setLang = useCallback(
    (newLang: Lang) => {
      setLangState(newLang);
      onLangChange?.(newLang);
    },
    [onLangChange],
  );

  const t = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>): string => {
      let text = translations[lang]?.[key] ?? translations['zh-CN'][key] ?? key;
      if (params) {
        for (const [k, v] of Object.entries(params)) {
          text = text.replace(`{${k}}`, String(v));
        }
      }
      return text;
    },
    [lang],
  );

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
