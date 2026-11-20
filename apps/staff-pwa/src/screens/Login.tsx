import { ApiError, post, type TokenOut } from '@oglos/client';
import { errorKey, useI18n } from '@oglos/i18n';
import { Button, Field, Wordmark } from '@oglos/ui';
import { Delete, Mail, Smartphone } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { LangSwitch } from '../components/Chrome';
import { loadDevice, saveDevice, useSession } from '../session';

type Mode = 'email' | 'pin' | 'device';

function lastHospital(): string {
  try {
    return localStorage.getItem('oglos.hospital') ?? '';
  } catch {
    return '';
  }
}

export function Login() {
  const { t } = useI18n();
  const device = loadDevice();
  const [mode, setMode] = useState<Mode>(device ? 'pin' : 'email');

  return (
    <div className="min-h-screen bg-bg">
      <header className="bg-deep px-4 pb-8 pt-6 text-white">
        <div className="mx-auto max-w-md">
          <div className="flex items-center justify-between">
            <Wordmark onDark height={34} />
            <LangSwitch dark />
          </div>
          <p className="mt-4 text-sm text-palegilt/90">{t('app.subtitle')}</p>
          <div className="mt-3 h-px w-16 bg-gilt" />
        </div>
      </header>
      <main className="mx-auto -mt-4 max-w-md px-4 pb-10">
        <div className="rounded-sheet border border-line bg-surface p-5 shadow-float">
          {mode === 'email' && <EmailLogin onPin={() => setMode(device ? 'pin' : 'device')} />}
          {mode === 'pin' && device && (
            <PinLogin onEmail={() => setMode('email')} onReset={() => setMode('device')} />
          )}
          {mode === 'device' && (
            <DeviceSetup onDone={() => setMode('pin')} onEmail={() => setMode('email')} />
          )}
        </div>
      </main>
    </div>
  );
}

function useError() {
  const { t } = useI18n();
  const [error, setError] = useState<string>();
  return {
    error,
    clear: () => setError(undefined),
    fail: (e: unknown) => setError(t(errorKey(e instanceof ApiError ? e.code : undefined))),
  };
}

function EmailLogin({ onPin }: { onPin: () => void }) {
  const { t } = useI18n();
  const { signIn } = useSession();
  const [hospital, setHospital] = useState(lastHospital());
  const [email, setEmail] = useState('');
  const [challenge, setChallenge] = useState<string>();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const { error, fail, clear } = useError();

  async function send(e: FormEvent) {
    e.preventDefault();
    clear();
    setBusy(true);
    try {
      const r = await post<{ challenge_id: string }>('/auth/otp/request', {
        hospital_code: hospital,
        email,
      });
      localStorage.setItem('oglos.hospital', hospital);
      setChallenge(r.challenge_id);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }
  async function verify(e: FormEvent) {
    e.preventDefault();
    clear();
    setBusy(true);
    try {
      const r = await post<TokenOut>('/auth/otp/verify', {
        hospital_code: hospital,
        challenge_id: challenge,
        code,
      });
      await signIn(r.access_token);
    } catch (err) {
      fail(err);
      setBusy(false);
    }
  }

  return (
    <>
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <Mail size={22} aria-hidden className="text-ward" /> {t('login.title')}
      </h2>
      {!challenge ? (
        <form onSubmit={send} className="flex flex-col gap-4">
          <Field
            label={t('login.hospital_code')}
            value={hospital}
            onChange={(e) => setHospital(e.target.value.toUpperCase())}
            autoCapitalize="characters"
            required
            autoComplete="organization"
          />
          <Field
            label={t('login.email')}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            inputMode="email"
            error={error}
          />
          <Button type="submit" size="xl" busy={busy}>
            {t('login.send_code')}
          </Button>
        </form>
      ) : (
        <form onSubmit={verify} className="flex flex-col gap-4">
          <p className="text-base text-ink2">{t('login.code_sent', { email })}</p>
          <Field
            label={t('login.code')}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            className="[&_input]:mono [&_input]:text-xl [&_input]:tracking-[0.4em]"
            error={error}
          />
          <Button type="submit" size="xl" busy={busy} disabled={code.length !== 6}>
            {t('login.verify')}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setChallenge(undefined);
              setCode('');
              clear();
            }}
          >
            {t('common.back')}
          </Button>
        </form>
      )}
      <hr className="my-5 border-line" />
      <Button variant="secondary" size="lg" className="w-full" onClick={onPin}>
        <Smartphone size={20} aria-hidden /> {t('login.use_pin')}
      </Button>
    </>
  );
}

function PinLogin({ onEmail, onReset }: { onEmail: () => void; onReset: () => void }) {
  const { t } = useI18n();
  const { signIn } = useSession();
  const device = loadDevice()!;
  const [employee, setEmployee] = useState('');
  const [pin, setPin] = useState('');
  const [busy, setBusy] = useState(false);
  const { error, fail, clear } = useError();

  async function submit(fullPin: string) {
    clear();
    setBusy(true);
    try {
      const r = await post<TokenOut>('/auth/pin/login', {
        hospital_code: device.hospitalCode,
        device_key: device.deviceKey,
        employee_code: employee,
        pin: fullPin,
      });
      await signIn(r.access_token);
    } catch (err) {
      fail(err);
      setPin('');
      setBusy(false);
      if (err instanceof ApiError && err.code === 'DEVICE_NOT_REGISTERED') onReset();
    }
  }
  function press(d: string) {
    if (busy) return;
    const next = (pin + d).slice(0, 6);
    setPin(next);
  }

  return (
    <>
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <Smartphone size={22} aria-hidden className="text-ward" /> {t('login.title')}
      </h2>
      <Field
        label={t('login.employee_code')}
        value={employee}
        onChange={(e) => setEmployee(e.target.value.toUpperCase())}
        autoCapitalize="characters"
        placeholder="HK-101"
        required
      />
      <div className="mt-5">
        <div className="mb-2 text-sm font-semibold">{t('login.pin')}</div>
        <div
          aria-live="polite"
          className="mb-3 flex h-8 items-center justify-center gap-3"
          aria-label={`${pin.length} / 6`}
        >
          {Array.from({ length: 6 }, (_, i) => (
            <span
              key={i}
              className={`h-3.5 w-3.5 rounded-full ${i < pin.length ? 'bg-ward' : 'border-2 border-linestrong'}`}
            />
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
            <button
              key={d}
              onClick={() => press(d)}
              className="mono h-16 rounded-panel border border-line bg-surface text-xl font-medium active:bg-sunk"
            >
              {d}
            </button>
          ))}
          <button
            onClick={() => setPin(pin.slice(0, -1))}
            aria-label="Delete"
            className="grid h-16 place-items-center rounded-panel text-ink2 active:bg-sunk"
          >
            <Delete size={24} aria-hidden />
          </button>
          <button
            onClick={() => press('0')}
            className="mono h-16 rounded-panel border border-line bg-surface text-xl font-medium active:bg-sunk"
          >
            0
          </button>
          <span />
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-bad-ink">
          {error}
        </p>
      )}
      <Button
        size="xl"
        className="mt-4"
        busy={busy}
        disabled={pin.length < 4 || !employee}
        onClick={() => submit(pin)}
      >
        {t('login.verify')}
      </Button>
      <Button variant="ghost" className="mt-3 w-full" onClick={onEmail}>
        <Mail size={18} aria-hidden /> {t('login.use_email')}
      </Button>
    </>
  );
}

function DeviceSetup({ onDone, onEmail }: { onDone: () => void; onEmail: () => void }) {
  const { t } = useI18n();
  const [hospital, setHospital] = useState(lastHospital());
  const [key, setKey] = useState('');
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        saveDevice({ hospitalCode: hospital, deviceKey: key.trim() });
        localStorage.setItem('oglos.hospital', hospital);
        onDone();
      }}
    >
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <Smartphone size={22} aria-hidden className="text-ward" /> {t('login.device_setup')}
      </h2>
      <Field
        label={t('login.hospital_code')}
        value={hospital}
        onChange={(e) => setHospital(e.target.value.toUpperCase())}
        required
      />
      <Field
        label={t('login.device_key')}
        value={key}
        onChange={(e) => setKey(e.target.value)}
        hint={t('login.device_key_hint')}
        required
        minLength={16}
        className="[&_input]:mono"
        autoComplete="off"
      />
      <Button type="submit" size="xl">
        {t('login.continue')}
      </Button>
      <Button type="button" variant="ghost" onClick={onEmail}>
        <Mail size={18} aria-hidden /> {t('login.use_email')}
      </Button>
    </form>
  );
}
