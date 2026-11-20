import { get, post, type Branch, type Checkin, type Flag } from '@oglos/client';
import { useI18n } from '@oglos/i18n';
import { Button } from '@oglos/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Flag as FlagIcon, LogIn, LogOut, Printer, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Empty, Panel, Shell } from '../components/Shell';
import { hhmm } from '../time';

export function Flags() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const flags = useQuery({ queryKey: ['flags'], queryFn: () => get<Flag[]>('/flags') });
  const review = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'dismissed' | 'confirmed' }) =>
      post(`/flags/${id}/review`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['flags'] }),
  });
  return (
    <Shell title={t('nav.flags')}>
      <p className="mb-4 max-w-2xl text-base text-ink2">{t('flags.human')}</p>
      <Panel title={t('flags.title')}>
        {flags.data?.length === 0 && <Empty>{t('flags.empty')}</Empty>}
        <ul className="divide-y divide-line">
          {flags.data?.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <FlagIcon size={18} className="text-brass" aria-hidden />
              <span className="min-w-0 flex-1 text-base">
                {t(`flags.rule.${f.rule}`)}
                <span className="mono ml-2 text-sm text-ink2">{hhmm(f.created_at)}</span>
              </span>
              <Link to={`/approvals?task=${f.task_id}`} className="text-sm text-ward underline">
                {t('flags.open_task')}
              </Link>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => review.mutate({ id: f.id, status: 'dismissed' })}
              >
                {t('flags.dismiss')}
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => review.mutate({ id: f.id, status: 'confirmed' })}
              >
                {t('flags.confirm')}
              </Button>
            </li>
          ))}
        </ul>
      </Panel>
    </Shell>
  );
}

export function Attendance() {
  const { t } = useI18n();
  const rows = useQuery({
    queryKey: ['attendance'],
    queryFn: () => get<Checkin[]>('/attendance/today'),
    refetchInterval: 60_000,
  });
  return (
    <Shell title={t('nav.attendance')}>
      <Panel title={t('common.today')}>
        {rows.data?.length === 0 && <Empty>{t('attendance.empty')}</Empty>}
        <table className="w-full text-base">
          <tbody className="divide-y divide-line">
            {rows.data?.map((r) => (
              <tr key={r.id}>
                <td className="mono w-20 px-4 py-2 text-ink2">{hhmm(r.server_ts)}</td>
                <td className="px-2 py-2">{r.display_name}</td>
                <td className="px-4 py-2 text-right">
                  <span className="inline-flex items-center gap-1.5 text-sm text-ink2">
                    {r.kind === 'check_in' ? (
                      <LogIn size={16} aria-hidden />
                    ) : (
                      <LogOut size={16} aria-hidden />
                    )}
                    {t(r.kind === 'check_in' ? 'staff.check_in' : 'staff.check_out')}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </Shell>
  );
}

export function EntranceQr() {
  const { t } = useI18n();
  const branches = useQuery({ queryKey: ['branches'], queryFn: () => get<Branch[]>('/branches') });
  const [branchId, setBranchId] = useState<string>();
  const id = branchId ?? branches.data?.[0]?.id;
  const qc = useQueryClient();
  const qr = useQuery({
    queryKey: ['entrance-qr', id],
    queryFn: () => get<{ svg: string; version: number }>(`/branches/${id}/entrance-qr`),
    enabled: Boolean(id),
  });
  const rotate = useMutation({
    mutationFn: () => post(`/branches/${id}/entrance-qr/rotate`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['entrance-qr', id] }),
  });
  const branch = branches.data?.find((b) => b.id === id);
  const src = qr.data ? `data:image/svg+xml;utf8,${encodeURIComponent(qr.data.svg)}` : undefined;
  return (
    <Shell
      title={t('nav.entrance_qr')}
      actions={
        <select
          value={id}
          onChange={(e) => setBranchId(e.target.value)}
          className="h-9 rounded-control border border-line bg-surface px-2 text-sm"
        >
          {branches.data?.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      }
    >
      <p className="mb-4 max-w-2xl text-base text-ink2 print:hidden">{t('qr.body')}</p>
      <div className="flex flex-wrap gap-2 print:hidden">
        <Button onClick={() => window.print()}>
          <Printer size={18} aria-hidden /> {t('qr.print')}
        </Button>
        <Button
          variant="secondary"
          busy={rotate.isPending}
          onClick={() => window.confirm(t('qr.rotate_confirm')) && rotate.mutate()}
        >
          <RefreshCw size={18} aria-hidden /> {t('qr.rotate')}
        </Button>
      </div>
      {src && (
        <article className="mx-auto mt-6 flex max-w-md flex-col items-center gap-3 rounded-sheet border-2 border-ward bg-white p-8 text-center">
          <img src="/brand/oglos-logo-light.png" alt="OGLOS" className="h-8" />
          <h2 className="text-xl font-semibold">
            {t('staff.check_in')} / {t('staff.check_out')}
          </h2>
          <p className="text-base">{branch?.name}</p>
          <img src={src} alt={t('qr.title')} className="w-72" />
          <p className="text-sm text-ink2">
            ಪ್ರವೇಶ QR · प्रवेश QR · <span className="mono">v{qr.data?.version}</span>
          </p>
        </article>
      )}
    </Shell>
  );
}
