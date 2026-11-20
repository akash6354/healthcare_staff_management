import { get, type Checkin, type Task } from '@oglos/client';
import { pick, useI18n } from '@oglos/i18n';
import { StatusChip, ToneIcon, toneOf, type Tone } from '@oglos/ui';
import { useQuery } from '@tanstack/react-query';
import { ChevronRight, DoorOpen, LogIn, LogOut, RotateCcw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { TopBand } from '../components/Chrome';
import { useSession } from '../session';
import { hhmm, lateBy, minutesFromNow } from '../time';

const ORDER: Record<Tone, number> = {
  missed: 0,
  overdue: 1,
  progress: 2,
  due: 3,
  idle: 4,
  review: 5,
  done: 6,
  off: 7,
};
const STRIPE: Record<Tone, string> = {
  missed: 'bg-bad',
  overdue: 'bg-bad',
  progress: 'bg-progress',
  due: 'bg-linestrong',
  idle: 'bg-line',
  review: 'bg-review',
  done: 'bg-good',
  off: 'bg-line',
};

export function Home() {
  const { t, lang } = useI18n();
  const { me, signOut } = useSession();
  const tasks = useQuery({
    queryKey: ['my-tasks'],
    queryFn: () => get<Task[]>('/me/tasks'),
    refetchInterval: 60_000,
  });
  const desks = useQuery({
    queryKey: ['my-desks'],
    queryFn: () => get<{ id: string; name: string; code: string }[]>('/me/desks'),
  });
  const attendance = useQuery({
    queryKey: ['my-attendance'],
    queryFn: () => get<Checkin[]>('/me/attendance'),
  });

  const last = attendance.data?.at(-1);
  const checkedIn = last?.kind === 'check_in';
  const sorted = [...(tasks.data ?? [])].sort(
    (a, b) => ORDER[toneOf(a)] - ORDER[toneOf(b)] || a.due_at.localeCompare(b.due_at),
  );
  const openCount = sorted.filter((x) => ['pending', 'in_progress'].includes(x.status)).length;

  return (
    <div className="min-h-screen bg-bg pb-28">
      <TopBand
        title={me?.display_name ?? ''}
        sub={desks.data?.map((d) => d.name).join(', ') || me?.hospital.name}
        right={
          <button
            onClick={signOut}
            className="h-12 rounded-control px-3 text-sm text-palegilt hover:bg-white/10"
          >
            {t('common.sign_out')}
          </button>
        }
      />
      <main className="mx-auto max-w-xl px-4 pt-4">
        <section className="mb-5 flex items-center gap-3 rounded-panel border border-line bg-surface p-3">
          <DoorOpen aria-hidden className={checkedIn ? 'text-good-ink' : 'text-ink2'} size={28} />
          <div className="flex-1 text-base">
            {last
              ? t(checkedIn ? 'staff.checked_in_at' : 'staff.checked_out_at', {
                  time: hhmm(last.server_ts),
                })
              : t('staff.scan_entrance')}
          </div>
          <Link
            to={checkedIn ? '/scan/check_out' : '/scan/check_in'}
            className="inline-flex h-12 items-center gap-2 rounded-control border border-ward px-4 font-semibold text-ward"
          >
            {checkedIn ? <LogOut size={20} aria-hidden /> : <LogIn size={20} aria-hidden />}
            {t(checkedIn ? 'staff.check_out' : 'staff.check_in')}
          </Link>
        </section>

        <h2 className="mb-2 flex items-baseline justify-between text-md font-semibold">
          {t('staff.my_tasks')}
          {tasks.data && tasks.data.length > 0 && (
            <span className="num text-sm font-normal text-ink2">
              {t('staff.to_do', { count: openCount })}
            </span>
          )}
        </h2>

        {tasks.isLoading && <p className="text-ink2">{t('common.loading')}</p>}
        {tasks.data && tasks.data.length === 0 && (
          <p className="rounded-panel border border-dashed border-linestrong bg-surface p-5 text-base text-ink2">
            {t('staff.no_desk')}
          </p>
        )}
        <ul className="flex flex-col gap-2">
          {sorted.map((task) => {
            const tone = toneOf(task);
            const mins = minutesFromNow(task.due_at);
            const open = task.status === 'pending' || task.status === 'in_progress';
            return (
              <li key={task.id}>
                <Link
                  to={`/task/${task.id}`}
                  className="flex min-h-[76px] items-stretch overflow-hidden rounded-panel border border-line bg-surface active:bg-sunk"
                >
                  <span className={`w-1.5 shrink-0 ${STRIPE[tone]}`} aria-hidden />
                  <span className="flex flex-1 items-center gap-3 px-3 py-3">
                    <span
                      className={
                        tone === 'overdue' || tone === 'missed' ? 'text-bad-ink' : 'text-ink2'
                      }
                    >
                      <ToneIcon tone={tone} size={24} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-base font-semibold leading-snug">
                        {pick(task.title_i18n, lang)}
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink2">
                        <span className="mono">{hhmm(task.due_at)}</span>
                        {open && mins >= 0 && <span>{t('staff.due_in', { minutes: mins })}</span>}
                        {open && mins < 0 && (
                          <span className="font-semibold text-bad-ink">{lateBy(t, -mins)}</span>
                        )}
                        {!open && <StatusChip tone={tone} label={t(`status.${tone}`)} />}
                        {task.rework_count > 0 && task.status === 'pending' && (
                          <span className="inline-flex items-center gap-1 text-due-ink">
                            <RotateCcw size={14} aria-hidden />
                            {task.review_note}
                          </span>
                        )}
                      </span>
                    </span>
                    <ChevronRight className="text-ink2" aria-hidden />
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
        {tasks.data && tasks.data.length > 0 && openCount === 0 && (
          <p className="mt-4 text-center text-base text-good-ink">{t('staff.all_done')}</p>
        )}
      </main>
    </div>
  );
}
