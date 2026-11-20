import { ApiError, post, type TokenOut } from '@oglos/client';
import { errorKey, LANGS, useI18n } from '@oglos/i18n';
import { Button, Field, Wordmark } from '@oglos/ui';
import { KeyRound } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { useSession } from '../session';

export function Login() {
  const { t, lang, setLang } = useI18n();
  const { signIn } = useSession();
  const [hospital, setHospital] = useState(() => localStorage.getItem('oglos.hospital') ?? '');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaToken, setMfaToken] = useState<string>();
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  const fail = (e: unknown) => {
    setError(t(errorKey(e instanceof ApiError ? e.code : undefined)));
    setBusy(false);
  };

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(undefined);
    setBusy(true);
    try {
      if (!mfaToken) {
        const r = await post<TokenOut>('/auth/password/login', {
          hospital_code: hospital,
          email,
          password,
        });
        localStorage.setItem('oglos.hospital', hospital);
        if (r.totp_required && r.mfa_token) {
          setMfaToken(r.mfa_token);
          setBusy(false);
          return;
        }
        await signIn(r.access_token);
      } else {
        const r = await post<TokenOut>('/auth/totp/verify', { mfa_token: mfaToken, code });
        await signIn(r.access_token);
      }
    } catch (err) {
      fail(err);
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(360px,44%)_1fr]">
      <section className="flex flex-col justify-between bg-deep px-8 py-8 text-white lg:px-14 lg:py-12">
        <Wordmark onDark height={40} />
        <div className="my-10 lg:my-0">
          <div className="mb-4 h-px w-20 bg-gilt" />
          <p
            className="max-w-sm text-xl font-medium leading-snug"
            style={{ fontVariationSettings: "'wdth' 112" }}
          >
            {t('app.subtitle')}
          </p>
          <p className="mt-4 max-w-sm text-base text-palegilt/85">{t('login.tagline')}</p>
        </div>
        <p className="text-xs text-palegilt/70">oglos.site</p>
      </section>
      <section className="flex items-center justify-center px-4 py-10">
        <form onSubmit={submit} className="w-full max-w-sm">
          <div className="mb-6 flex items-center justify-between">
            <h1 className="text-xl font-semibold">{t('login.title')}</h1>
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value as typeof lang)}
              aria-label={t('common.language')}
              className="h-9 rounded-control border border-line bg-surface px-2 text-sm"
            >
              {LANGS.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          {!mfaToken ? (
            <div className="flex flex-col gap-4">
              <Field
                label={t('login.hospital_code')}
                value={hospital}
                onChange={(e) => setHospital(e.target.value.toUpperCase())}
                required
                autoComplete="organization"
              />
              <Field
                label={t('login.email')}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="username"
              />
              <Field
                label={t('login.password')}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                error={error}
              />
              <Button type="submit" size="lg" busy={busy}>
                {t('login.verify')}
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <p className="flex gap-2 text-base text-ink2">
                <KeyRound aria-hidden className="shrink-0 text-ward" /> {t('login.totp_hint')}
              </p>
              <Field
                label={t('login.totp')}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\s/g, ''))}
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                autoFocus
                className="[&_input]:mono [&_input]:text-lg [&_input]:tracking-[0.3em]"
                error={error}
              />
              <Button type="submit" size="lg" busy={busy}>
                {t('login.verify')}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setMfaToken(undefined);
                  setCode('');
                }}
              >
                {t('common.back')}
              </Button>
            </div>
          )}
        </form>
      </section>
    </div>
  );
}

/** Admin/manager accounts without TOTP land here first (the API blocks everything else). */
export function EnrolTotp() {
  const { t } = useI18n();
  const { signIn } = useSession();
  const [uri, setUri] = useState<string>();
  const [code, setCode] = useState('');
  const [codes, setCodes] = useState<string[]>();
  const [token, setToken] = useState<string>();
  const [error, setError] = useState<string>();
  const secret = uri ? new URL(uri).searchParams.get('secret') : null;

  return (
    <div className="grid min-h-screen place-items-center bg-bg px-4">
      <div className="w-full max-w-md rounded-sheet border border-line bg-surface p-6">
        {!codes ? (
          <>
            <h1 className="mb-2 text-lg font-semibold">{t('login.enrol_title')}</h1>
            <p className="mb-4 text-base text-ink2">{t('login.enrol_body')}</p>
            {!uri ? (
              <Button
                onClick={async () =>
                  setUri((await post<{ otpauth_uri: string }>('/auth/totp/enroll')).otpauth_uri)
                }
              >
                {t('login.continue')}
              </Button>
            ) : (
              <form
                className="flex flex-col gap-4"
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    const r = await post<{ recovery_codes: string[]; access_token: string }>(
                      '/auth/totp/confirm',
                      { code },
                    );
                    setCodes(r.recovery_codes);
                    setToken(r.access_token);
                  } catch (err) {
                    setError(t(errorKey(err instanceof ApiError ? err.code : undefined)));
                  }
                }}
              >
                <p className="mono select-all break-all rounded-control bg-sunk p-3 text-base">
                  {secret}
                </p>
                <Field
                  label={t('login.totp')}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  inputMode="numeric"
                  required
                  error={error}
                />
                <Button type="submit">{t('login.verify')}</Button>
              </form>
            )}
          </>
        ) : (
          <>
            <h1 className="mb-2 text-lg font-semibold">{t('login.recovery_title')}</h1>
            <p className="mb-4 text-base text-ink2">{t('login.recovery_body')}</p>
            <ul className="mono mb-5 grid grid-cols-2 gap-2 rounded-control bg-sunk p-3 text-base">
              {codes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <Button onClick={() => token && signIn(token)}>{t('login.continue')}</Button>
          </>
        )}
      </div>
    </div>
  );
}
