import { LANGS, useI18n } from '@oglos/i18n';
import { LogoMark } from '@oglos/ui';
import { ChevronLeft, WifiOff } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';

export function LangSwitch({ dark = false }: { dark?: boolean }) {
  const { lang, setLang, t } = useI18n();
  return (
    <div role="group" aria-label={t('common.language')} className="flex gap-1">
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => setLang(l.code)}
          aria-pressed={lang === l.code}
          className={`h-10 min-w-12 rounded-control px-3 text-sm font-semibold ${
            lang === l.code
              ? dark
                ? 'bg-palegilt text-deep'
                : 'bg-ward text-white'
              : dark
                ? 'text-palegilt/85 hover:bg-white/10'
                : 'text-ink2 hover:bg-sunk'
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export function OfflineBanner() {
  const { t } = useI18n();
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);
  if (online) return null;
  return (
    <div
      role="status"
      className="flex items-center gap-2 border-l-4 border-brass bg-cream px-4 py-2 text-sm text-ink"
    >
      <WifiOff size={18} aria-hidden /> {t('common.offline')}
    </div>
  );
}

/** Ward Green top band: where you are, in large type. */
export function TopBand({
  title,
  sub,
  back,
  right,
}: {
  title: string;
  sub?: ReactNode;
  back?: boolean;
  right?: ReactNode;
}) {
  const nav = useNavigate();
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-10 bg-ward text-white">
      <div className="mx-auto flex max-w-xl items-center gap-3 px-4 py-3">
        {back ? (
          <button
            onClick={() => nav(-1)}
            aria-label={t('common.back')}
            className="-ml-2 grid h-12 w-12 place-items-center rounded-control hover:bg-white/10"
          >
            <ChevronLeft size={28} aria-hidden />
          </button>
        ) : (
          <LogoMark size={36} />
        )}
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold leading-tight">{title}</h1>
          {sub && <div className="truncate text-sm text-palegilt">{sub}</div>}
        </div>
        {right}
      </div>
      <OfflineBanner />
    </header>
  );
}
