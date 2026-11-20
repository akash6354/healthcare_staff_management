import {
  ApiError,
  del,
  get,
  post,
  put,
  type Branch,
  type Desk,
  type RosterEntry,
  type Shift,
  type StaffUser,
} from '@oglos/client';
import { errorKey, pick, useI18n } from '@oglos/i18n';
import { Button, Field } from '@oglos/ui';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2 } from 'lucide-react';
import { useState, type FormEvent, type ReactNode } from 'react';
import { Empty, Panel, Shell } from '../components/Shell';

interface Department {
  id: string;
  name: string;
}
interface Floor {
  id: string;
  label: string;
  level: number;
}
interface Template {
  id: string;
  desk_id: string;
  title_i18n: Record<string, string>;
  times: string[];
  due_minutes: number;
  checklist: unknown[];
  active: boolean;
}

const useList = <T,>(key: string, path: string) =>
  useQuery({ queryKey: [key], queryFn: () => get<T[]>(path) });

function Select({
  label,
  value,
  onChange,
  children,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className="h-11 rounded-control border border-linestrong bg-surface px-2 text-base font-normal"
      >
        <option value="">–</option>
        {children}
      </select>
    </label>
  );
}

function useSave(keys: string[]) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [error, setError] = useState<string>();
  return {
    error,
    run: async (fn: () => Promise<unknown>) => {
      setError(undefined);
      try {
        await fn();
        keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
        return true;
      } catch (e) {
        setError(t(errorKey(e instanceof ApiError ? e.code : undefined)));
        return false;
      }
    },
  };
}

// ---------------------------------------------------------------- staff

const ROLE_KEYS = ['worker', 'supervisor', 'management_viewer', 'hospital_admin'] as const;

export function StaffScreen() {
  const { t } = useI18n();
  const users = useList<StaffUser>('users', '/users?limit=500');
  const depts = useList<Department>('departments', '/departments');
  const [form, setForm] = useState({
    employee_code: '',
    display_name: '',
    email: '',
    role: 'worker',
    department_id: '',
    pin: '',
  });
  const save = useSave(['users']);
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const scoped = form.role === 'worker' || form.role === 'supervisor';
    const ok = await save.run(async () => {
      const u = await post<StaffUser>('/users', {
        employee_code: form.employee_code,
        display_name: form.display_name,
        email: form.email || null,
        employment_type: 'employee',
        department_id: form.department_id || null,
        roles: [
          scoped && form.department_id
            ? { role: form.role, scope_type: 'department', scope_id: form.department_id }
            : { role: form.role },
        ],
      });
      if (form.pin) await put(`/users/${u.id}/pin`, { pin: form.pin });
    });
    if (ok)
      setForm({
        employee_code: '',
        display_name: '',
        email: '',
        role: 'worker',
        department_id: form.department_id,
        pin: '',
      });
  }

  return (
    <Shell title={t('nav.staff')}>
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <Panel
          title={t('nav.staff')}
          aside={<span className="num text-sm text-ink2">{users.data?.length}</span>}
        >
          <table className="w-full text-base">
            <thead className="bg-sunk text-left text-sm text-ink2">
              <tr>
                <th className="px-4 py-2">{t('setup.code')}</th>
                <th className="px-2 py-2">{t('setup.name')}</th>
                <th className="px-2 py-2">{t('setup.role')}</th>
                <th className="px-4 py-2">{t('setup.department')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {users.data?.map((u) => (
                <tr key={u.id}>
                  <td className="mono px-4 py-2 text-sm">{u.employee_code}</td>
                  <td className="px-2 py-2">{u.display_name}</td>
                  <td className="px-2 py-2 text-sm">
                    {u.roles.map((r) => t(`role.${r.role}` as never)).join(', ')}
                  </td>
                  <td className="px-4 py-2 text-sm text-ink2">
                    {depts.data?.find((d) => d.id === u.department_id)?.name}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title={t('setup.add_staff')}>
          <form onSubmit={submit} className="flex flex-col gap-3 p-4">
            <Field
              label={t('setup.code')}
              value={form.employee_code}
              onChange={(e) => set('employee_code')(e.target.value.toUpperCase())}
              required
            />
            <Field
              label={t('setup.name')}
              value={form.display_name}
              onChange={(e) => set('display_name')(e.target.value)}
              required
              minLength={2}
            />
            <Field
              label={t('login.email')}
              type="email"
              value={form.email}
              onChange={(e) => set('email')(e.target.value)}
              hint={t('setup.email_hint')}
            />
            <Select label={t('setup.role')} value={form.role} onChange={set('role')} required>
              {ROLE_KEYS.map((r) => (
                <option key={r} value={r}>
                  {t(`role.${r}`)}
                </option>
              ))}
            </Select>
            <Select
              label={t('setup.department')}
              value={form.department_id}
              onChange={set('department_id')}
            >
              {depts.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
            {form.role === 'worker' && (
              <Field
                label={t('setup.pin')}
                value={form.pin}
                onChange={(e) => set('pin')(e.target.value.replace(/\D/g, '').slice(0, 6))}
                inputMode="numeric"
                hint={t('setup.pin_hint')}
              />
            )}
            {save.error && (
              <p role="alert" className="text-sm text-bad-ink">
                {save.error}
              </p>
            )}
            <Button type="submit">
              <Plus size={18} aria-hidden /> {t('setup.add_staff')}
            </Button>
          </form>
        </Panel>
      </div>
    </Shell>
  );
}

// ---------------------------------------------------------------- desks

export function DesksScreen() {
  const { t } = useI18n();
  const desks = useList<Desk>('desks', '/desks');
  const branches = useList<Branch>('branches', '/branches');
  const floors = useList<Floor>('floors', '/floors');
  const depts = useList<Department>('departments', '/departments');
  const [form, setForm] = useState({
    name: '',
    code: '',
    branch_id: '',
    floor_id: '',
    department_id: '',
  });
  const save = useSave(['desks']);
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const branchId = form.branch_id || branches.data?.[0]?.id || '';

  return (
    <Shell title={t('nav.desks')}>
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <Panel
          title={t('nav.desks')}
          aside={<span className="num text-sm text-ink2">{desks.data?.length}</span>}
        >
          {desks.data?.length === 0 && <Empty>{t('setup.no_desks')}</Empty>}
          <table className="w-full text-base">
            <tbody className="divide-y divide-line">
              {desks.data?.map((d) => (
                <tr key={d.id}>
                  <td className="mono w-28 px-4 py-2 text-sm">{d.code}</td>
                  <td className="px-2 py-2">{d.name}</td>
                  <td className="px-2 py-2 text-sm text-ink2">
                    {floors.data?.find((f) => f.id === d.floor_id)?.label}
                  </td>
                  <td className="px-4 py-2 text-sm text-ink2">
                    {branches.data?.find((b) => b.id === d.branch_id)?.name}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title={t('setup.add_desk')}>
          <form
            className="flex flex-col gap-3 p-4"
            onSubmit={async (e) => {
              e.preventDefault();
              const ok = await save.run(() =>
                post('/desks', {
                  name: form.name,
                  code: form.code,
                  branch_id: branchId,
                  floor_id: form.floor_id || null,
                  department_id: form.department_id || null,
                }),
              );
              if (ok) setForm((f) => ({ ...f, name: '', code: '' }));
            }}
          >
            <Field
              label={t('setup.name')}
              value={form.name}
              onChange={(e) => set('name')(e.target.value)}
              placeholder="Housekeeping Floor 2"
              required
            />
            <Field
              label={t('setup.code')}
              value={form.code}
              onChange={(e) => set('code')(e.target.value.toUpperCase())}
              placeholder="HK-F2"
              required
            />
            <Select label={t('setup.branch')} value={branchId} onChange={set('branch_id')} required>
              {branches.data?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Select>
            <Select label={t('setup.floor')} value={form.floor_id} onChange={set('floor_id')}>
              {floors.data?.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label}
                </option>
              ))}
            </Select>
            <Select
              label={t('setup.department')}
              value={form.department_id}
              onChange={set('department_id')}
            >
              {depts.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
            {save.error && (
              <p role="alert" className="text-sm text-bad-ink">
                {save.error}
              </p>
            )}
            <Button type="submit">
              <Plus size={18} aria-hidden /> {t('setup.add_desk')}
            </Button>
          </form>
        </Panel>
      </div>
    </Shell>
  );
}

// ---------------------------------------------------------------- roster

function todayIST(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date());
}

export function RosterScreen() {
  const { t } = useI18n();
  const [day, setDay] = useState(todayIST());
  const desks = useList<Desk>('desks', '/desks');
  const users = useList<StaffUser>('users', '/users?limit=500');
  const shifts = useList<Shift>('shifts', '/shifts');
  const roster = useQuery({
    queryKey: ['roster', day],
    queryFn: () => get<RosterEntry[]>(`/roster?from_date=${day}&to_date=${day}`),
  });
  const qc = useQueryClient();
  const save = useSave([]);
  const [shiftId, setShiftId] = useState('');
  const shift = shiftId || shifts.data?.[0]?.id || '';
  const workers = users.data?.filter((u) => u.roles.some((r) => r.role === 'worker')) ?? [];
  const refresh = () => qc.invalidateQueries({ queryKey: ['roster', day] });
  const remove = useMutation({
    mutationFn: (id: string) => del(`/roster/${id}`),
    onSuccess: refresh,
  });

  return (
    <Shell
      title={t('nav.roster')}
      actions={
        <>
          <input
            type="date"
            value={day}
            onChange={(e) => setDay(e.target.value)}
            className="h-9 rounded-control border border-line px-2 text-sm"
          />
          <select
            value={shift}
            onChange={(e) => setShiftId(e.target.value)}
            className="h-9 rounded-control border border-line bg-surface px-2 text-sm"
          >
            {shifts.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} {s.starts_at.slice(0, 5)}–{s.ends_at.slice(0, 5)}
              </option>
            ))}
          </select>
        </>
      }
    >
      <p className="mb-4 max-w-2xl text-base text-ink2">{t('setup.roster_help')}</p>
      {save.error && (
        <p role="alert" className="mb-3 text-sm text-bad-ink">
          {save.error}
        </p>
      )}
      <Panel>
        <table className="w-full text-base">
          <tbody className="divide-y divide-line">
            {desks.data?.map((d) => {
              const entries =
                roster.data?.filter((r) => r.desk_id === d.id && r.shift_id === shift) ?? [];
              return (
                <tr key={d.id}>
                  <td className="mono w-28 px-4 py-2 text-sm">{d.code}</td>
                  <td className="px-2 py-2">{d.name}</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap gap-1.5">
                      {entries.map((r) => (
                        <span
                          key={r.id}
                          className="inline-flex items-center gap-1 rounded-full border border-line bg-sunk py-0.5 pl-2.5 pr-1 text-sm"
                        >
                          {users.data?.find((u) => u.id === r.user_id)?.display_name}
                          <button
                            aria-label={t('setup.remove')}
                            onClick={() => remove.mutate(r.id)}
                            className="grid h-6 w-6 place-items-center rounded-full hover:bg-bad/10"
                          >
                            <Trash2 size={13} aria-hidden />
                          </button>
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <select
                      value=""
                      aria-label={t('setup.assign')}
                      className="h-9 rounded-control border border-line bg-surface px-2 text-sm"
                      onChange={(e) =>
                        e.target.value &&
                        save.run(async () => {
                          await post('/roster', {
                            user_id: e.target.value,
                            shift_id: shift,
                            work_date: day,
                            desk_id: d.id,
                            department_id: d.department_id,
                          });
                          refresh();
                        })
                      }
                    >
                      <option value="">{t('setup.assign')}</option>
                      {workers.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.display_name} ({u.employee_code})
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </Shell>
  );
}

// ---------------------------------------------------------------- templates

export function TemplatesScreen() {
  const { t, lang } = useI18n();
  const templates = useList<Template>('templates', '/task-templates');
  const desks = useList<Desk>('desks', '/desks');
  const save = useSave(['templates']);
  const [form, setForm] = useState({
    desk_id: '',
    en: '',
    kn: '',
    hi: '',
    times: '08:00, 12:00, 16:00',
    due: '45',
    checklist: '',
  });
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    const checklist = form.checklist
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
      .map((line, i) => {
        const [en, kn, hi] = line.split('|').map((s) => s.trim());
        return {
          key: `item_${i + 1}`,
          label_i18n: { en: en!, ...(kn ? { kn } : {}), ...(hi ? { hi } : {}) },
        };
      });
    const ok = await save.run(() =>
      post('/task-templates', {
        desk_id: form.desk_id,
        schedule_kind: 'daily',
        title_i18n: {
          en: form.en,
          ...(form.kn ? { kn: form.kn } : {}),
          ...(form.hi ? { hi: form.hi } : {}),
        },
        times: form.times
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        due_minutes: Number(form.due),
        checklist,
      }),
    );
    if (ok) setForm((f) => ({ ...f, en: '', kn: '', hi: '', checklist: '' }));
  }

  return (
    <Shell title={t('nav.templates')}>
      <div className="grid gap-6 xl:grid-cols-[1fr_420px]">
        <Panel title={t('nav.templates')}>
          {templates.data?.length === 0 && <Empty>{t('setup.no_templates')}</Empty>}
          <ul className="divide-y divide-line">
            {templates.data?.map((tp) => (
              <li key={tp.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <span className="mono w-24 text-sm text-ink2">
                  {desks.data?.find((d) => d.id === tp.desk_id)?.code}
                </span>
                <span className="min-w-0 flex-1">{pick(tp.title_i18n, lang)}</span>
                <span className="mono text-sm text-ink2">{tp.times.join(' ')}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title={t('setup.add_template')}>
          <form onSubmit={submit} className="flex flex-col gap-3 p-4">
            <Select label={t('staff.desk')} value={form.desk_id} onChange={set('desk_id')} required>
              {desks.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code} {d.name}
                </option>
              ))}
            </Select>
            <Field
              label={`${t('setup.title')} (English)`}
              value={form.en}
              onChange={(e) => set('en')(e.target.value)}
              required
            />
            <Field
              label={`${t('setup.title')} (ಕನ್ನಡ)`}
              value={form.kn}
              onChange={(e) => set('kn')(e.target.value)}
            />
            <Field
              label={`${t('setup.title')} (हिन्दी)`}
              value={form.hi}
              onChange={(e) => set('hi')(e.target.value)}
            />
            <Field
              label={t('setup.times')}
              value={form.times}
              onChange={(e) => set('times')(e.target.value)}
              hint={t('setup.times_hint')}
              className="[&_input]:mono"
              required
            />
            <Field
              label={t('setup.due_minutes')}
              type="number"
              min={5}
              max={1440}
              value={form.due}
              onChange={(e) => set('due')(e.target.value)}
              required
            />
            <label className="flex flex-col gap-1 text-sm font-semibold">
              {t('task.checklist')}
              <textarea
                rows={4}
                value={form.checklist}
                onChange={(e) => set('checklist')(e.target.value)}
                className="rounded-control border border-linestrong p-2 text-base font-normal"
                placeholder="Floor mopped | ನೆಲ ಒರೆಸಲಾಗಿದೆ | फ़र्श पोछा"
              />
              <span className="text-sm font-normal text-ink2">{t('setup.checklist_hint')}</span>
            </label>
            {save.error && (
              <p role="alert" className="text-sm text-bad-ink">
                {save.error}
              </p>
            )}
            <Button type="submit">
              <Plus size={18} aria-hidden /> {t('setup.add_template')}
            </Button>
          </form>
        </Panel>
      </div>
    </Shell>
  );
}
