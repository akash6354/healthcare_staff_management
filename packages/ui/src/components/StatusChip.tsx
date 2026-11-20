import {
  Ban,
  CircleCheck,
  CircleDashed,
  ClipboardCheck,
  LoaderCircle,
  OctagonX,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react';

/** One semantic status vocabulary for the whole product (ui-direction §3).
 *  Colour is never alone: every chip carries an icon and a text label. */
export type Tone = 'done' | 'review' | 'progress' | 'due' | 'overdue' | 'missed' | 'idle' | 'off';

const TONES: Record<Tone, { icon: LucideIcon; cls: string }> = {
  done: { icon: CircleCheck, cls: 'bg-good/10 text-good-ink border-good/40' },
  review: { icon: ClipboardCheck, cls: 'bg-review/10 text-review-ink border-review/40' },
  progress: { icon: LoaderCircle, cls: 'bg-progress/10 text-progress-ink border-progress/40' },
  due: { icon: CircleDashed, cls: 'bg-surface text-ink2 border-linestrong' },
  overdue: { icon: TriangleAlert, cls: 'bg-bad/10 text-bad-ink border-bad/60 border-2' },
  missed: { icon: OctagonX, cls: 'bg-bad text-white border-bad' },
  idle: { icon: CircleDashed, cls: 'bg-surface text-ink2 border-line' },
  off: { icon: Ban, cls: 'bg-sunk text-ink2 border-line' },
};

export interface TaskLike {
  status: string;
  sla_state: string;
}

export function toneOf(t: TaskLike): Tone {
  if (t.status === 'approved') return 'done';
  if (t.status === 'submitted') return 'review';
  if (t.status === 'cancelled') return 'off';
  if (t.sla_state === 'missed') return 'missed';
  if (t.sla_state === 'overdue') return 'overdue';
  if (t.status === 'in_progress') return 'progress';
  return 'due';
}

export function StatusChip({
  tone,
  label,
  size = 'md',
}: {
  tone: Tone;
  label: string;
  size?: 'md' | 'lg';
}) {
  const { icon: Icon, cls } = TONES[tone];
  const sz = size === 'lg' ? 'text-sm px-2.5 py-1 gap-1.5' : 'text-xs px-2 py-0.5 gap-1';
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full border font-medium ${sz} ${cls}`}
    >
      <Icon aria-hidden size={size === 'lg' ? 16 : 13} strokeWidth={2} />
      {label}
    </span>
  );
}

export function ToneIcon({ tone, size = 16 }: { tone: Tone; size?: number }) {
  const { icon: Icon } = TONES[tone];
  return <Icon aria-hidden size={size} strokeWidth={2} />;
}
