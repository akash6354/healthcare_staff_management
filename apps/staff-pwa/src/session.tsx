import { get, onAuthChange, post, refreshSession, setAccessToken, type Me } from '@oglos/client';
import { useI18n } from '@oglos/i18n';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

interface Session {
  me: Me | null;
  ready: boolean;
  signIn: (accessToken: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);
  const { setLang } = useI18n();

  const loadMe = useCallback(async () => {
    const m = await get<Me>('/me');
    setMe(m);
    if (!localStorage.getItem('oglos.lang')) setLang(m.preferred_language);
  }, [setLang]);

  useEffect(() => {
    (async () => {
      if (await refreshSession()) await loadMe().catch(() => setMe(null));
      setReady(true);
    })();
    return onAuthChange((signedIn) => {
      if (!signedIn) setMe(null);
    }) as unknown as () => void;
  }, [loadMe]);

  const signIn = useCallback(
    async (token: string) => {
      setAccessToken(token);
      await loadMe();
    },
    [loadMe],
  );
  const signOut = useCallback(async () => {
    await post('/auth/logout').catch(() => undefined);
    setAccessToken(null);
    setMe(null);
  }, []);

  return <Ctx.Provider value={{ me, ready, signIn, signOut }}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useSession outside provider');
  return ctx;
}

/** Shared-device registration lives in this browser only (security.md §2: PIN works only on it). */
export interface DeviceConfig {
  hospitalCode: string;
  deviceKey: string;
}
const DEVICE_KEY = 'oglos.device';
export function loadDevice(): DeviceConfig | null {
  try {
    const raw = localStorage.getItem(DEVICE_KEY);
    return raw ? (JSON.parse(raw) as DeviceConfig) : null;
  } catch {
    return null;
  }
}
export function saveDevice(cfg: DeviceConfig | null) {
  try {
    if (cfg) localStorage.setItem(DEVICE_KEY, JSON.stringify(cfg));
    else localStorage.removeItem(DEVICE_KEY);
  } catch {
    /* storage unavailable */
  }
}
