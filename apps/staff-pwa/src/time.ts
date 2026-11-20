const fmt = new Intl.DateTimeFormat('en-IN', {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Asia/Kolkata',
});

/** Server times shown in IST, 24-hour, e.g. "14:05". */
export function hhmm(iso: string): string {
  return fmt.format(new Date(iso));
}

export function minutesFromNow(iso: string): number {
  return Math.round((new Date(iso).getTime() - Date.now()) / 60_000);
}

type T = (
  key: 'staff.overdue_by' | 'staff.overdue_by_hours',
  params: Record<string, number>,
) => string;

/** "Late by 25 min" or "Late by 10 h 4 min": big raw minute counts are hard to read. */
export function lateBy(t: T, minutes: number): string {
  if (minutes < 60) return t('staff.overdue_by', { minutes });
  return t('staff.overdue_by_hours', { hours: Math.floor(minutes / 60), minutes: minutes % 60 });
}
