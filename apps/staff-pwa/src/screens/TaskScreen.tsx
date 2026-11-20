import {
  ApiError,
  get,
  post,
  upload,
  type ChecklistItem,
  type Proof,
  type TaskDetail,
} from '@oglos/client';
import { errorKey, pick, useI18n } from '@oglos/i18n';
import { Button, StatusChip, toneOf } from '@oglos/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bath,
  Camera,
  Check,
  Droplets,
  Info,
  ShieldAlert,
  SprayCan,
  Trash2,
  Wind,
  type LucideIcon,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TopBand } from '../components/Chrome';
import { hhmm, lateBy, minutesFromNow } from '../time';

/** Pictograms for checklist items, so staff who don't read the menu language can still follow. */
const ICONS: Record<string, LucideIcon> = {
  mop: Wind,
  toilet: Bath,
  soap: Droplets,
  bin: Trash2,
  spray: SprayCan,
};

export function TaskScreen() {
  const { id } = useParams();
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const nav = useNavigate();
  const [error, setError] = useState<string>();
  const task = useQuery({ queryKey: ['task', id], queryFn: () => get<TaskDetail>(`/tasks/${id}`) });
  const [ticks, setTicks] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (task.data?.checklist_result) setTicks(task.data.checklist_result);
  }, [task.data?.checklist_result]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['task', id] });
    qc.invalidateQueries({ queryKey: ['my-tasks'] });
  };
  const fail = (e: unknown) => setError(t(errorKey(e instanceof ApiError ? e.code : undefined)));
  const start = useMutation({
    mutationFn: () => post(`/tasks/${id}/start`),
    onSuccess: refresh,
    onError: fail,
  });
  const submit = useMutation({
    mutationFn: () => post(`/tasks/${id}/submit`, { checklist: ticks }),
    onSuccess: () => {
      refresh();
      nav('/', { replace: true });
    },
    onError: fail,
  });

  if (!task.data) {
    return (
      <div className="min-h-screen bg-bg">
        <TopBand title={t('common.loading')} back />
      </div>
    );
  }
  const d = task.data;
  const tone = toneOf(d);
  // Only this attempt's photos count (a rework needs new photos).
  const attempt = d.proofs.filter((p) => !d.started_at || p.server_received_at >= d.started_at);
  const before = attempt.filter((p) => p.phase === 'before').at(-1);
  const after = attempt.filter((p) => p.phase === 'after').at(-1);
  const requiredDone = d.checklist.every((i) => i.required === false || ticks[i.key]);
  const ready =
    requiredDone && (!d.requires_before_photo || before) && (!d.requires_after_photo || after);
  const mins = minutesFromNow(d.due_at);
  const working = d.status === 'in_progress';

  let step = 1;
  return (
    <div className="min-h-screen bg-bg pb-32">
      <TopBand
        back
        title={pick(d.title_i18n, lang)}
        sub={
          <span className="flex items-center gap-2">
            {d.desk_name}
            <span aria-hidden>·</span>
            <span className="mono">{hhmm(d.due_at)}</span>
          </span>
        }
      />
      <main className="mx-auto flex max-w-xl flex-col gap-4 px-4 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip tone={tone} label={t(`status.${tone}`)} size="lg" />
          {(d.status === 'pending' || working) && (
            <span className={`text-base ${mins < 0 ? 'font-semibold text-bad-ink' : 'text-ink2'}`}>
              {mins < 0 ? lateBy(t, -mins) : t('staff.due_in', { minutes: mins })}
            </span>
          )}
        </div>

        {d.review_note && d.status === 'pending' && (
          <p className="rounded-panel border-l-4 border-due bg-surface p-3 text-base">
            {t('task.rework', { note: d.review_note })}
          </p>
        )}

        {pick(d.instructions_i18n, lang) && (
          <section className="flex gap-3 rounded-panel border border-line bg-surface p-3">
            <Info aria-hidden className="mt-0.5 shrink-0 text-ward" />
            <div>
              <h2 className="text-sm font-semibold text-ink2">{t('task.instructions')}</h2>
              <p className="text-base">{pick(d.instructions_i18n, lang)}</p>
            </div>
          </section>
        )}

        {(working || d.status !== 'pending') && (
          <ol className="flex flex-col gap-4">
            {d.requires_before_photo && (
              <Step n={step++} title={t('task.step_before')} done={Boolean(before)}>
                <PhotoSlot
                  taskId={d.id}
                  phase="before"
                  proof={before}
                  enabled={working}
                  onDone={refresh}
                  onError={fail}
                />
              </Step>
            )}
            {d.checklist.length > 0 && (
              <Step n={step++} title={t('task.step_checklist')} done={requiredDone}>
                <ul className="flex flex-col gap-2">
                  {d.checklist.map((item) => (
                    <CheckRow
                      key={item.key}
                      item={item}
                      checked={Boolean(ticks[item.key])}
                      disabled={!working}
                      onToggle={() => setTicks((p) => ({ ...p, [item.key]: !p[item.key] }))}
                    />
                  ))}
                </ul>
              </Step>
            )}
            {d.requires_after_photo && (
              <Step n={step++} title={t('task.step_after')} done={Boolean(after)}>
                <PhotoSlot
                  taskId={d.id}
                  phase="after"
                  proof={after}
                  enabled={working && (!d.requires_before_photo || Boolean(before))}
                  onDone={refresh}
                  onError={fail}
                />
              </Step>
            )}
          </ol>
        )}

        <p className="flex items-start gap-2 text-sm text-ink2">
          <ShieldAlert size={18} aria-hidden className="mt-0.5 shrink-0" /> {t('task.no_patients')}
        </p>
        {error && (
          <p role="alert" className="rounded-control bg-bad/10 p-3 text-base text-bad-ink">
            {error}
          </p>
        )}
      </main>

      {(d.status === 'pending' || working) && (
        <div className="fixed inset-x-0 bottom-0 border-t border-line bg-surface p-4">
          <div className="mx-auto max-w-xl">
            {d.status === 'pending' ? (
              <Button
                size="xl"
                busy={start.isPending}
                onClick={() => {
                  setError(undefined);
                  start.mutate();
                }}
              >
                {t('task.start')}
              </Button>
            ) : (
              <Button
                size="xl"
                busy={submit.isPending}
                disabled={!ready}
                onClick={() => {
                  setError(undefined);
                  submit.mutate();
                }}
              >
                {t('task.submit')}
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Step({
  n,
  title,
  done,
  children,
}: {
  n: number;
  title: string;
  done: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="rounded-panel border border-line bg-surface p-3">
      <h3 className="mb-3 flex items-center gap-2 text-md font-semibold">
        <span
          className={`mono grid h-8 w-8 place-items-center rounded-full text-sm ${done ? 'bg-good text-white' : 'bg-sunk text-ink'}`}
        >
          {done ? <Check size={18} aria-hidden /> : n}
        </span>
        {title}
      </h3>
      {children}
    </li>
  );
}

function CheckRow({
  item,
  checked,
  disabled,
  onToggle,
}: {
  item: ChecklistItem;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  const { t, lang } = useI18n();
  const Icon = (item.icon && ICONS[item.icon]) || Check;
  return (
    <li>
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        disabled={disabled}
        onClick={onToggle}
        className={`flex min-h-14 w-full items-center gap-3 rounded-control border px-3 text-left text-base ${
          checked ? 'border-good bg-good/10' : 'border-linestrong bg-surface'
        } disabled:opacity-70`}
      >
        <Icon size={24} aria-hidden className="shrink-0 text-ward" />
        <span className="flex-1">
          {pick(item.label_i18n, lang)}
          {item.required === false && (
            <span className="ml-2 text-sm text-ink2">({t('task.optional')})</span>
          )}
        </span>
        <span
          className={`grid h-8 w-8 shrink-0 place-items-center rounded-control border-2 ${checked ? 'border-good bg-good text-white' : 'border-linestrong'}`}
        >
          {checked && <Check size={20} aria-hidden strokeWidth={3} />}
        </span>
      </button>
    </li>
  );
}

function PhotoSlot({
  taskId,
  phase,
  proof,
  enabled,
  onDone,
  onError,
}: {
  taskId: string;
  phase: 'before' | 'after';
  proof?: Proof;
  enabled: boolean;
  onDone: () => void;
  onError: (e: unknown) => void;
}) {
  const { t } = useI18n();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function onFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    const form = new FormData();
    form.set('phase', phase);
    form.set('photo', file);
    form.set('client_captured_at', new Date().toISOString());
    try {
      await upload(`/tasks/${taskId}/proofs`, form);
      onDone();
    } catch (e) {
      onError(e);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {proof?.thumb_url && (
        <figure className="flex items-center gap-3">
          <img
            src={proof.thumb_url}
            alt=""
            className="h-20 w-28 rounded-control border border-line object-cover"
          />
          <figcaption className="text-sm text-good-ink">
            {t('task.photo_saved')}{' '}
            <span className="mono text-ink2">{hhmm(proof.server_received_at)}</span>
          </figcaption>
        </figure>
      )}
      {enabled && (
        <>
          {/* capture="environment" opens the camera directly on Android; the server stamps the time. */}
          <input
            ref={input}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            hidden
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <Button
            variant={proof ? 'secondary' : 'primary'}
            size="lg"
            className="w-full"
            busy={busy}
            onClick={() => input.current?.click()}
          >
            <Camera size={22} aria-hidden />
            {proof
              ? t('task.retake')
              : t(phase === 'before' ? 'task.before_photo' : 'task.after_photo')}
          </Button>
          {!proof && <p className="text-sm text-ink2">{t('task.camera_only')}</p>}
        </>
      )}
    </div>
  );
}
