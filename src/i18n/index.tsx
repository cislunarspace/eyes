import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { invoke } from '@tauri-apps/api/core';
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

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>('zh-CN');

  // 启动时从后端读取语言配置
  useEffect(() => {
    invoke<{ language: string }>('get_config')
      .then((cfg) => {
        if (cfg.language === 'en') setLangState('en');
      })
      .catch(() => {});
  }, []);

  const setLang = useCallback((newLang: Lang) => {
    setLangState(newLang);
  }, []);

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
