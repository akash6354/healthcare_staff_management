import { LANGS, useI18n, type MessageKey } from '@oglos/i18n';
import { Wordmark } from '@oglos/ui';
import {
  CalendarDays,
  ClipboardCheck,
  DoorOpen,
  Flag,
  LayoutGrid,
  ListChecks,
  MonitorSmartphone,
  QrCode,
  Users,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, type ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { useSession } from '../session';

interface Item {
  to: string;
  key: MessageKey;
  icon: LucideIcon;
  perm: string;
}
const GROUPS: { key: MessageKey; items: Item[] }[] = [
  {
    key: 'nav.group.live',
    items: [
      { to: '/', key: 'nav.today', icon: LayoutGrid, perm: 'board.view' },
      { to: '/approvals', key: 'nav.approvals', icon: ClipboardCheck, perm: 'task.verify' },
      { to: '/flags', key: 'nav.flags', icon: Flag, perm: 'task.verify' },
      { to: '/attendance', key: 'nav.attendance', icon: DoorOpen, perm: 'staff.view' },
    ],
  },
  {
    key: 'nav.group.setup',
    items: [
      { to: '/staff', key: 'nav.staff', icon: Users, perm: 'staff.manage' },
      { to: '/desks', key: 'nav.desks', icon: MonitorSmartphone, perm: 'org.manage' },
      { to: '/roster', key: 'nav.roster', icon: CalendarDays, perm: 'roster.manage' },
      { to: '/templates', key: 'nav.templates', icon: ListChecks, perm: 'config.manage' },
      { to: '/entrance-qr', key: 'nav.entrance_qr', icon: QrCode, perm: 'org.manage' },
    ],
  },
];

export function Shell({
  title,
  actions,
  children,
}: {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const { t, lang, setLang } = useI18n();
  const { me, signOut } = useSession();
  useEffect(() => {
    document.title = `${title} · OGLOS`;
  }, [title]);
  const can = (perm: string) => Boolean(me?.permissions[perm]);

  return (
    <div className="min-h-screen bg-bg lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="border-b border-line bg-surface lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-4 py-4 lg:block">
          <Wordmark height={26} />
          <p className="mt-2 hidden text-xs leading-snug text-ink2 lg:block">{me?.hospital.name}</p>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 lg:block lg:px-3">
          {GROUPS.map((g) => {
            const items = g.items.filter((i) => can(i.perm));
            if (!items.length) return null;
            return (
              <div key={g.key} className="flex gap-1 lg:mb-5 lg:block">
                <p className="hidden px-2 pb-1 text-xs font-semibold text-ink2 lg:block">
                  {t(g.key)}
                </p>
                {items.map((i) => (
                  <NavLink
                    key={i.to}
                    to={i.to}
                    end={i.to === '/'}
                    className={({ isActive }) =>
                      `flex h-9 shrink-0 items-center gap-2.5 rounded-control px-2 text-base ${
                        isActive ? 'bg-ward font-semibold text-white' : 'text-ink hover:bg-sunk'
                      }`
                    }
                  >
                    <i.icon size={18} aria-hidden />
                    <span className="whitespace-nowrap">{t(i.key)}</span>
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
      </aside>
      <div className="min-w-0">
        <header className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-3 lg:px-8">
          <h1 className="mr-auto text-lg font-semibold">{title}</h1>
          {actions}
          <select
            aria-label={t('common.language')}
            value={lang}
            onChange={(e) => setLang(e.target.value as typeof lang)}
            className="h-9 rounded-control border border-line bg-surface px-2 text-sm"
          >
            {LANGS.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
          <span className="hidden text-sm text-ink2 sm:inline">{me?.display_name}</span>
          <button
            onClick={signOut}
            className="h-9 rounded-control px-3 text-sm text-ink hover:bg-sunk"
          >
            {t('common.sign_out')}
          </button>
        </header>
        <main className="px-4 py-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}

export function Panel({
  title,
  aside,
  children,
  className = '',
}: {
  title?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-panel border border-line bg-surface ${className}`}>
      {title && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <h2 className="text-md font-semibold">{title}</h2>
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="px-4 py-8 text-center text-base text-ink2">{children}</p>;
}
