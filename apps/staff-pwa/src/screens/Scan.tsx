import { ApiError, post } from '@oglos/client';
import { errorKey, useI18n } from '@oglos/i18n';
import { Button } from '@oglos/ui';
import { useQueryClient } from '@tanstack/react-query';
import jsQR from 'jsqr';
import { CircleCheck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TopBand } from '../components/Chrome';
import { hhmm } from '../time';

type Detector = { detect: (src: CanvasImageSource) => Promise<{ rawValue: string }[]> };

/** Entrance QR check-in/out. Uses the camera live (no photo is stored); BarcodeDetector where
 *  the browser has it, jsQR (Apache-2.0) otherwise. */
export function Scan() {
  const { kind } = useParams<{ kind: 'check_in' | 'check_out' }>();
  const { t } = useI18n();
  const nav = useNavigate();
  const qc = useQueryClient();
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string>();
  const [done, setDone] = useState<string>();

  useEffect(() => {
    let stream: MediaStream | undefined;
    let stopped = false;
    let busy = false;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const BD = (window as unknown as { BarcodeDetector?: new (o: object) => Detector })
      .BarcodeDetector;
    const detector = BD ? new BD({ formats: ['qr_code'] }) : null;

    async function found(token: string) {
      busy = true;
      try {
        const r = await post<{ server_ts: string }>('/attendance/scan', { token, kind });
        stopped = true;
        qc.invalidateQueries({ queryKey: ['my-attendance'] });
        setDone(r.server_ts);
      } catch (e) {
        setError(t(errorKey(e instanceof ApiError ? e.code : undefined)));
        setTimeout(() => (busy = false), 2500);
      }
    }

    async function tick() {
      if (stopped) return;
      const v = video.current;
      if (v && v.readyState >= 2 && !busy) {
        try {
          if (detector) {
            const codes = await detector.detect(v);
            if (codes[0]) await found(codes[0].rawValue);
          } else if (ctx) {
            canvas.width = v.videoWidth;
            canvas.height = v.videoHeight;
            ctx.drawImage(v, 0, 0);
            const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(img.data, img.width, img.height);
            if (code?.data) await found(code.data);
          }
        } catch {
          /* keep scanning */
        }
      }
      requestAnimationFrame(tick);
    }

    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then((s) => {
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play();
        }
        requestAnimationFrame(tick);
      })
      .catch(() => setError(t('staff.camera_blocked')));

    return () => {
      stopped = true;
      stream?.getTracks().forEach((tr) => tr.stop());
    };
  }, [kind, qc, t]);

  return (
    <div className="min-h-screen bg-deep text-white">
      <TopBand
        back
        title={t(kind === 'check_out' ? 'staff.check_out' : 'staff.check_in')}
        sub={t('staff.scan_entrance')}
      />
      <main className="mx-auto max-w-xl px-4 pt-4">
        {done ? (
          <div className="mt-10 flex flex-col items-center gap-4 text-center">
            <CircleCheck size={72} className="text-good" aria-hidden />
            <p className="text-lg font-semibold">
              {t(kind === 'check_out' ? 'staff.checked_out_at' : 'staff.checked_in_at', {
                time: hhmm(done),
              })}
            </p>
            <Button
              size="xl"
              onClick={() => nav('/', { replace: true })}
              className="mt-6 max-w-sm bg-palegilt text-deep"
            >
              {t('login.continue')}
            </Button>
          </div>
        ) : (
          <>
            <div className="relative overflow-hidden rounded-sheet border border-white/20 bg-black">
              <video ref={video} playsInline muted className="aspect-square w-full object-cover" />
              <div
                aria-hidden
                className="pointer-events-none absolute inset-[18%] rounded-panel border-4 border-gilt/90"
              />
            </div>
            <p className="mt-4 text-center text-base text-palegilt">{t('staff.scan_help')}</p>
            {error && (
              <p role="alert" className="mt-3 rounded-control bg-bad p-3 text-base">
                {error}
              </p>
            )}
          </>
        )}
      </main>
    </div>
  );
}
