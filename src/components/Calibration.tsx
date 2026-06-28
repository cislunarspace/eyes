import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { useI18n } from '../i18n';

interface CalibrationProps {
  onComplete: (yaw: number, pitch: number) => void;
  onFail: () => void;
  onCancel: () => void;
}

const DURATION_SECONDS = 5;
const TICK_MS = 100;

interface PoseUpdate {
  pose_state: string;
  yaw: number | null;
  pitch: number | null;
}

export function Calibration({ onComplete, onFail, onCancel }: CalibrationProps) {
  const { t } = useI18n();
  const [countdown, setCountdown] = useState(DURATION_SECONDS);
  const [samples, setSamples] = useState(0);
  const [lastYaw, setLastYaw] = useState<number | null>(null);
  const [lastPitch, setLastPitch] = useState<number | null>(null);
  const noFaceTicks = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const unlistenRef = useRef<(() => void) | null>(null);

  const finishCalibration = useCallback(async () => {
    // 停止计时器
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    // 停止监听
    if (unlistenRef.current) {
      unlistenRef.current();
      unlistenRef.current = null;
    }
    // 检查结果
    try {
      const status = await invoke<{
        calibration_active: boolean;
      }>('get_status');
      if (!status.calibration_active) {
        // 校准完成，从 config 读取新 neutral
        const config = await invoke<{
          neutral_yaw: number;
          neutral_pitch: number;
        }>('get_config');
        onComplete(config.neutral_yaw, config.neutral_pitch);
      } else {
        onFail();
      }
    } catch {
      onFail();
    }
  }, [onComplete, onFail]);

  useEffect(() => {
    // 监听姿态更新，喂入校准
    listen<PoseUpdate>('pose-updated', (event) => {
      const { yaw, pitch, pose_state } = event.payload;
      if (yaw !== null && pitch !== null) {
        setLastYaw(yaw);
        setLastPitch(pitch);
        noFaceTicks.current = 0;
        invoke('feed_calibration', { yaw, pitch }).catch(() => {});
      } else if (pose_state === 'NoFace') {
        noFaceTicks.current += 1;
        // 连续 10 帧无人脸（1 秒），判定校准失败
        if (noFaceTicks.current >= 10) {
          invoke('cancel_calibration').catch(() => {});
          onFail();
        }
      }
    }).then((unlisten) => {
      unlistenRef.current = unlisten;
    });

    // 倒计时
    timerRef.current = setInterval(() => {
      setCountdown((prev) => {
        const next = prev - TICK_MS / 1000;
        if (next <= 0) {
          // 校准时间到，获取结果
          finishCalibration();
          return 0;
        }
        return next;
      });
      setSamples((prev) => prev + 1);
    }, TICK_MS);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (unlistenRef.current) {
        unlistenRef.current();
      }
    };
  }, [finishCalibration, onFail]);

  return (
    <div className="calibration">
      <p className="calibration-instruction">{t('calibration.starting')}</p>
      <div className="calibration-countdown">
        {t('calibration.countdown', { seconds: Math.ceil(countdown) })}
      </div>
      <div className="calibration-samples">
        {t('calibration.samples', { count: samples })}
      </div>
      {lastYaw !== null && (
        <div className="calibration-pose">
          yaw: {lastYaw.toFixed(1)}° / pitch: {lastPitch?.toFixed(1)}°
        </div>
      )}
      <button onClick={onCancel} className="btn-secondary calibration-cancel">
        {t('calibration.cancel')}
      </button>
    </div>
  );
}
