import { get, type Dashboard, type Desk, type Task } from '@oglos/client';
import { pick, useI18n } from '@oglos/i18n';
import { StatusChip, ToneIcon, toneOf, type Tone } from '@oglos/ui';
import { useQuery } from '@tanstack/react-query';
import { Flag, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Panel, Shell } from '../components/Shell';
import { hhmm } from '../time';

interface Floor {
  id: string;
  label: string;
  level: number;
  building_id: string;
}

const RANK: Tone[] = ['missed', 'overdue', 'review', 'progress', 'due', 'done'];
const TILE: Record<Tone, string> = {
  missed: 'border-bad bg-bad text-white',
  overdue: 'border-bad border-2 bg-bad/10 text-bad-ink',
  review: 'border-review bg-review/10 text-review-ink',
  progress: 'border-progress bg-progress/10 text-progress-ink',
  due: 'border-linestrong bg-surface text-ink',
  done: 'border-good bg-good/10 text-good-ink',
  idle: 'border-line bg-surface text-ink2',
  off: 'border-line bg-sunk text-ink2',
};

function deskTone(tasks: Task[]): Tone {
  const live = tasks.filter((t) => t.status !== 'cancelled');
  if (!live.length) return 'idle';
  const tones = live.map(toneOf);
  if (tones.every((t) => t === 'done')) return 'done';
  return RANK.find((r) => tones.includes(r)) ?? 'due';
}

export function Today() {
  const { t, lang } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const dash = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => get<Dashboard>('/dashboard/today'),
    refetchInterval: 60_000,
  });
  const tasks = useQuery({
    queryKey: ['tasks-today'],
    queryFn: () => get<Task[]>('/tasks?limit=1000'),
    refetchInterval: 60_000,
  });
  const desks = useQuery({ queryKey: ['desks'], queryFn: () => get<Desk[]>('/desks') });
  const floors = useQuery({ queryKey: ['floors'], queryFn: () => get<Floor[]>('/floors') });

  const byDesk = useMemo(() => {
    const m = new Map<string, Task[]>();
    for (const task of tasks.data ?? [])
      m.set(task.desk_id, [...(m.get(task.desk_id) ?? []), task]);
    return m;
  }, [tasks.data]);

  const bands = useMemo(() => {
    const fl = [...(floors.data ?? [])].sort((a, b) => b.level - a.level);
    const rows = fl.map((f) => ({
      key: f.id,
      label: f.label,
      desks: (desks.data ?? []).filter((d) => d.floor_id === f.id),
    }));
    const loose = (desks.data ?? []).filter(
      (d) => !d.floor_id || !fl.some((f) => f.id === d.floor_id),
    );
    if (loose.length) rows.push({ key: 'none', label: '–', desks: loose });
    return rows.filter((r) => r.desks.length);
  }, [floors.data, desks.data]);

  const c = dash.data?.counts;
  const sel = selected ? desks.data?.find((d) => d.id === selected) : undefined;
  const selTasks = selected
    ? [...(byDesk.get(selected) ?? [])].sort((a, b) => a.due_at.localeCompare(b.due_at))
    : [];

  return (
    <Shell title={t('nav.today')}>
      {c && (
        <section className="mb-6">
          <p
            className="text-xl font-semibold leading-tight"
            style={{ fontVariationSettings: "'wdth' 108" }}
          >
            {t('dash.headline', { done: c.done, total: c.total - c.cancelled })}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {c.missed > 0 && (
              <StatusChip tone="missed" label={t('dash.missed', { count: c.missed })} size="lg" />
            )}
            {c.overdue > 0 && (
              <StatusChip
                tone="overdue"
                label={t('dash.overdue', { count: c.overdue })}
                size="lg"
              />
            )}
            {c.awaiting_approval > 0 && (
              <Link to="/approvals">
                <StatusChip
                  tone="review"
                  label={t('dash.review', { count: c.awaiting_approval })}
                  size="lg"
                />
              </Link>
            )}
            {c.in_progress > 0 && (
              <StatusChip
                tone="progress"
                label={t('dash.progress', { count: c.in_progress })}
                size="lg"
              />
            )}
            {dash.data!.open_flags > 0 && (
              <Link
                to="/flags"
                className="inline-flex items-center gap-1.5 rounded-full border border-brass px-2.5 py-1 text-sm font-medium text-brass"
              >
                <Flag size={15} aria-hidden /> {t('dash.flags', { count: dash.data!.open_flags })}
              </Link>
            )}
          </div>
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <Panel title={t('dash.building')} aside={<Legend />}>
          {(floors.isLoading || desks.isLoading) && (
            <p className="px-4 py-8 text-center text-ink2">{t('common.loading')}</p>
          )}
          {!floors.isLoading && !desks.isLoading && bands.length === 0 && (
            <p className="px-4 py-8 text-center text-ink2">{t('dash.empty')}</p>
          )}
          <ol className="divide-y divide-line">
            {!floors.isLoading &&
              bands.map((band) => (
                <li key={band.key} className="grid grid-cols-[56px_1fr] items-stretch">
                  <div className="mono flex items-center justify-center border-r border-line bg-sunk text-md font-medium text-ink2">
                    {band.label}
                  </div>
                  <div className="flex flex-wrap gap-2 p-3">
                    {band.desks.map((d) => {
                      const list = byDesk.get(d.id) ?? [];
                      const tone = deskTone(list);
                      const done = list.filter((x) => x.status === 'approved').length;
                      const live = list.filter((x) => x.status !== 'cancelled').length;
                      return (
                        <button
                          key={d.id}
                          onClick={() => setSelected(d.id)}
                          aria-pressed={selected === d.id}
                          className={`flex w-44 flex-col gap-1 rounded-tile border px-2.5 py-2 text-left transition-shadow hover:shadow-float ${TILE[tone]} ${selected === d.id ? 'ring-2 ring-brass ring-offset-1' : ''}`}
                        >
                          <span className="flex items-center justify-between gap-2">
                            <span className="mono text-sm font-medium">{d.code}</span>
                            <ToneIcon tone={tone} size={16} />
                          </span>
                          <span className="truncate text-sm font-semibold">{d.name}</span>
                          <span className="mono text-xs opacity-90">
                            {live ? `${done}/${live}` : '–'}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </li>
              ))}
          </ol>
        </Panel>

        <Panel
          title={sel ? sel.name : t('dash.by_desk')}
          aside={
            sel && (
              <button
                onClick={() => setSelected(null)}
                aria-label={t('common.back')}
                className="grid h-8 w-8 place-items-center rounded-control hover:bg-sunk"
              >
                <X size={18} aria-hidden />
              </button>
            )
          }
        >
          {sel ? (
            <ul className="divide-y divide-line">
              {selTasks.map((task) => {
                const tone = toneOf(task);
                return (
                  <li key={task.id} className="flex items-center gap-3 px-4 py-2.5">
                    <span className="mono w-12 text-sm text-ink2">{hhmm(task.due_at)}</span>
                    <span className="min-w-0 flex-1 truncate text-base">
                      {pick(task.title_i18n, lang)}
                    </span>
                    {task.status === 'submitted' ? (
                      <Link to={`/approvals?task=${task.id}`}>
                        <StatusChip tone={tone} label={t(`status.${tone}`)} />
                      </Link>
                    ) : (
                      <StatusChip tone={tone} label={t(`status.${tone}`)} />
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <table className="w-full text-base">
              <thead className="bg-sunk text-left text-sm text-ink2">
                <tr>
                  <th className="px-4 py-2 font-semibold">{t('dash.col.desk')}</th>
                  <th className="px-2 py-2 text-right font-semibold">{t('dash.col.done')}</th>
                  <th className="px-4 py-2 text-right font-semibold">{t('dash.col.late')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {dash.data?.desks.map((d) => (
                  <tr
                    key={d.id}
                    className="cursor-pointer hover:bg-sunk"
                    onClick={() => setSelected(d.id)}
                  >
                    <td className="px-4 py-2">
                      <span className="mono mr-2 text-sm text-ink2">{d.code}</span>
                      <span className="text-sm">{d.name}</span>
                    </td>
                    <td className="num px-2 py-2 text-right">
                      <Meter value={d.done} max={d.total} />
                    </td>
                    <td
                      className={`num px-4 py-2 text-right ${d.late ? 'font-semibold text-bad-ink' : 'text-ink2'}`}
                    >
                      {d.late}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </Shell>
  );
}

function Meter({ value, max }: { value: number; max: number }) {
  const pct = max ? Math.round((value / max) * 100) : 0;
  return (
    <span className="inline-flex items-center gap-2">
      <span className="relative h-1.5 w-20 overflow-hidden rounded-full bg-sunk" aria-hidden>
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-good"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="mono text-sm">
        {value}/{max}
      </span>
    </span>
  );
}

function Legend() {
  const { t } = useI18n();
  const items: Tone[] = ['done', 'review', 'progress', 'due', 'overdue', 'missed'];
  return (
    <ul className="hidden flex-wrap gap-3 text-xs text-ink2 md:flex">
      {items.map((tone) => (
        <li key={tone} className="inline-flex items-center gap-1">
          <ToneIcon tone={tone} size={13} /> {t(`status.${tone}`)}
        </li>
      ))}
    </ul>
  );
}
