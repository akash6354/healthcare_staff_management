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
