import { get, post, type Notice } from '@oglos/client';
import { pick, useI18n } from '@oglos/i18n';
import { Button } from '@oglos/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import { LangSwitch, TopBand } from '../components/Chrome';

/** DPDP: staff see the data notice at first sign-in and after every new version. */
export function NoticeGate({ children }: { children: ReactNode }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const notice = useQuery({
    queryKey: ['notice'],
    queryFn: () => get<Notice | null>('/notice/current'),
  });
  const ack = useMutation({
    mutationFn: (id: string) => post(`/notice/${id}/ack`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notice'] }),
  });

  if (notice.isLoading) return null;
  if (!notice.data || notice.data.acknowledged) return <>{children}</>;

  return (
    <div className="min-h-screen bg-bg">
      <TopBand
        title={t('notice.title')}
        right={<ShieldCheck aria-hidden className="text-palegilt" />}
      />
      <main className="mx-auto max-w-xl px-4 pb-32 pt-4">
        <div className="mb-3 flex justify-end">
          <LangSwitch />
        </div>
        <article className="whitespace-pre-line rounded-panel border border-line bg-surface p-4 text-base leading-relaxed">
          {pick(notice.data.body_i18n, lang)}
        </article>
      </main>
      <div className="fixed inset-x-0 bottom-0 border-t border-line bg-surface p-4">
        <div className="mx-auto max-w-xl">
          <Button size="xl" busy={ack.isPending} onClick={() => ack.mutate(notice.data!.id)}>
            {t('notice.agree')}
          </Button>
        </div>
      </div>
    </div>
  );
}
