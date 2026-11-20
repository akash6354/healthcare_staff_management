import { ApiError, get, post, type Task, type TaskDetail } from '@oglos/client';
import { errorKey, pick, useI18n } from '@oglos/i18n';
import { Button, StatusChip } from '@oglos/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Flag, ImageOff, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Empty, Panel, Shell } from '../components/Shell';
import { hhmm } from '../time';

export function Approvals() {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const queue = useQuery({
    queryKey: ['approvals'],
    queryFn: () => get<Task[]>('/tasks?status=submitted&limit=500'),
    refetchInterval: 30_000,
  });
  const selectedId = params.get('task') ?? queue.data?.[0]?.id;
  const detail = useQuery({
    queryKey: ['task', selectedId],
    queryFn: () => get<TaskDetail>(`/tasks/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const [note, setNote] = useState('');
  const [rejecting, setRejecting] = useState(false);
  const [message, setMessage] = useState<string>();
  useEffect(() => {
    setNote('');
    setRejecting(false);
  }, [selectedId]);

  const done = (msg: string) => {
    setMessage(msg);
    qc.invalidateQueries({ queryKey: ['approvals'] });
    qc.invalidateQueries({ queryKey: ['dashboard'] });
    const rest = queue.data?.filter((x) => x.id !== selectedId) ?? [];
    setParams(rest[0] ? { task: rest[0].id } : {});
  };
  const fail = (e: unknown) => setMessage(t(errorKey(e instanceof ApiError ? e.code : undefined)));
  const approve = useMutation({
    mutationFn: () => post(`/tasks/${selectedId}/approve`, {}),
    onSuccess: () => done(t('approve.approved')),
    onError: fail,
  });
  const reject = useMutation({
    mutationFn: () => post(`/tasks/${selectedId}/reject`, { note }),
    onSuccess: () => done(t('approve.rejected')),
    onError: fail,
  });

  const d = detail.data;
  const before = d?.proofs.filter((p) => p.phase === 'before').at(-1);
  const after = d?.proofs.filter((p) => p.phase === 'after').at(-1);

  return (
    <Shell title={t('nav.approvals')}>
      {message && (
        <p
          role="status"
          className="mb-4 rounded-control border-l-4 border-ward bg-surface px-4 py-2 text-base"
        >
          {message}
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Panel
          title={t('approve.title')}
          aside={<span className="num text-sm text-ink2">{queue.data?.length ?? ''}</span>}
        >
          {queue.data?.length === 0 && <Empty>{t('approve.empty')}</Empty>}
          <ul className="max-h-[70vh] divide-y divide-line overflow-y-auto">
            {queue.data?.map((task) => (
              <li key={task.id}>
                <button
                  onClick={() => setParams({ task: task.id })}
                  aria-current={task.id === selectedId}
                  className={`flex w-full flex-col gap-0.5 px-4 py-2.5 text-left hover:bg-sunk ${task.id === selectedId ? 'bg-sunk shadow-[inset_3px_0_0_var(--brass)]' : ''}`}
                >
                  <span className="text-base font-semibold">{pick(task.title_i18n, lang)}</span>
                  <span className="flex items-center gap-2 text-sm text-ink2">
                    <span className="mono">#{task.number}</span>
                    {task.submitted_at && (
                      <span>{t('approve.submitted_at', { time: hhmm(task.submitted_at) })}</span>
                    )}
                    {task.sla_state === 'late' && (
                      <span className="font-semibold text-bad-ink">{t('status.overdue')}</span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        {d && d.status === 'submitted' && (
          <Panel
            title={
              <span>
                {pick(d.title_i18n, lang)}{' '}
                <span className="mono text-sm font-normal text-ink2">#{d.number}</span>
              </span>
            }
            aside={<StatusChip tone="review" label={t('status.review')} />}
          >
            <div className="flex flex-col gap-5 p-4">
              <p className="text-base text-ink2">
                {d.desk_name} ·{' '}
                {d.submitted_by_name && t('approve.by', { name: d.submitted_by_name })} ·{' '}
                {d.submitted_at && <span className="mono">{hhmm(d.submitted_at)}</span>}
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { p: before, label: t('approve.before') },
                  { p: after, label: t('approve.after') },
                ].map(({ p, label }) => (
                  <figure
                    key={label}
                    className="overflow-hidden rounded-panel border border-line bg-sunk"
                  >
                    {p?.url ? (
                      <a href={p.url} target="_blank" rel="noreferrer">
                        <img src={p.url} alt={label} className="aspect-[4/3] w-full object-cover" />
                      </a>
                    ) : (
                      <div className="grid aspect-[4/3] place-items-center text-ink2">
                        <ImageOff aria-hidden />
                      </div>
                    )}
                    <figcaption className="flex justify-between px-3 py-1.5 text-sm">
                      <span className="font-semibold">{label}</span>
                      {p && <span className="mono text-ink2">{hhmm(p.server_received_at)}</span>}
                    </figcaption>
                  </figure>
                ))}
              </div>

              {d.checklist.length > 0 && (
                <ul className="grid gap-1.5 sm:grid-cols-2">
                  {d.checklist.map((item) => {
                    const ok = d.checklist_result?.[item.key];
                    return (
                      <li key={item.key} className="flex items-center gap-2 text-base">
                        {ok ? (
                          <Check size={18} className="text-good-ink" aria-label="yes" />
                        ) : (
                          <X size={18} className="text-bad-ink" aria-label="no" />
                        )}
                        {pick(item.label_i18n, lang)}
                      </li>
                    );
                  })}
                </ul>
              )}

              {d.flags.length > 0 && (
                <div className="rounded-control border border-brass/60 bg-cream/60 p-3">
                  <ul className="flex flex-col gap-1">
                    {d.flags.map((f) => (
                      <li key={f.id} className="flex items-center gap-2 text-base text-ink">
                        <Flag size={16} className="text-brass" aria-hidden />{' '}
                        {t(`flags.rule.${f.rule}`)}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-1 text-sm text-ink2">{t('flags.human')}</p>
                </div>
              )}

              {rejecting ? (
                <div className="flex flex-col gap-2">
                  <label htmlFor="reason" className="text-sm font-semibold">
                    {t('approve.reason')}
                  </label>
                  <textarea
                    id="reason"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    maxLength={500}
                    className="rounded-control border border-linestrong p-3 text-base"
                    autoFocus
                  />
                  <p className="text-sm text-ink2">{t('approve.reason_hint')}</p>
                  <div className="flex gap-2">
                    <Button
                      variant="danger"
                      busy={reject.isPending}
                      disabled={!note.trim()}
                      onClick={() => reject.mutate()}
                    >
                      {t('approve.reject')}
                    </Button>
                    <Button variant="ghost" onClick={() => setRejecting(false)}>
                      {t('common.cancel')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-2">
                  <Button size="lg" busy={approve.isPending} onClick={() => approve.mutate()}>
                    <Check size={18} aria-hidden /> {t('approve.approve')}
                  </Button>
                  <Button size="lg" variant="danger" onClick={() => setRejecting(true)}>
                    {t('approve.reject')}
                  </Button>
                </div>
              )}
            </div>
          </Panel>
        )}
      </div>
    </Shell>
  );
}
