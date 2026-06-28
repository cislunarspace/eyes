import React from 'react';
import ReactDOM from 'react-dom/client';
import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { I18nProvider, useI18n } from './i18n';
import type { TranslationKey } from './i18n/zh';
import { Settings } from './components/Settings';
import './styles.css';

type View = 'main' | 'settings';

function App() {
  const [lang, setLang] = useState<'zh-CN' | 'en'>('zh-CN');
  const [view, setView] = useState<View>('main');

  // 启动时从后端读取语言配置
  useEffect(() => {
    invoke<{ language: string }>('get_config')
      .then((cfg) => {
        if (cfg.language === 'en') setLang('en');
      })
      .catch(() => {});
  }, []);

  // 前端设置打开事件（托盘菜单"设置"→ 聚焦窗口，前端自行切换视图）
  useEffect(() => {
    const unlisten = listen('open-settings', () => setView('settings'));
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const handleLangChange = useCallback((newLang: 'zh-CN' | 'en') => {
    setLang(newLang);
  }, []);

  return (
    <I18nProvider initialLang={lang} onLangChange={handleLangChange}>
      {view === 'settings' ? (
        <Settings onBack={() => setView('main')} />
      ) : (
        <MainView onOpenSettings={() => setView('settings')} />
      )}
    </I18nProvider>
  );
}

function MainView({ onOpenSettings }: { onOpenSettings: () => void }) {
  const { t } = useI18n();
  const [poseState, setPoseState] = useState<string>('NoFace');
  const [yaw, setYaw] = useState<number | null>(null);
  const [pitch, setPitch] = useState<number | null>(null);

  useEffect(() => {
    const unlisten = listen<{
      pose_state: string;
      yaw: number | null;
      pitch: number | null;
    }>('pose-updated', (event) => {
      setPoseState(event.payload.pose_state);
      setYaw(event.payload.yaw);
      setPitch(event.payload.pitch);
    });
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const poseLabel = (() => {
    const map: Record<string, TranslationKey> = {
      FacingScreen: 'pose.facing_screen',
      OffAxisLeft: 'pose.off_axis_left',
      OffAxisRight: 'pose.off_axis_right',
      HeadUp: 'pose.head_up',
      HeadDown: 'pose.head_down',
      NoFace: 'pose.no_face',
    };
    return t(map[poseState] ?? 'pose.no_face');
  })();

  return (
    <main className="shell">
      <section className="hero" aria-labelledby="title">
        <p className="eyebrow">Eyes</p>
        <h1 id="title">{t('main.title')}</h1>
        <div className="status-card">
          <div className="pose-badge">{poseLabel}</div>
          {yaw !== null && (
            <div className="pose-readout">
              yaw: {yaw.toFixed(1)}° / pitch: {pitch?.toFixed(1)}°
            </div>
          )}
        </div>
        <button className="btn-settings" onClick={onOpenSettings}>
          ⚙ {t('main.settings')}
        </button>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
