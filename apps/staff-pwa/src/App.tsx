import { useI18n } from '@oglos/i18n';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Home } from './screens/Home';
import { Login } from './screens/Login';
import { NoticeGate } from './screens/Notice';
import { Scan } from './screens/Scan';
import { TaskScreen } from './screens/TaskScreen';
import { SessionProvider, useSession } from './session';

function Gate() {
  const { me, ready } = useSession();
  const { t } = useI18n();
  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center text-ink2">{t('common.loading')}</div>
    );
  }
  if (!me) return <Login />;
  return (
    <NoticeGate>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/task/:id" element={<TaskScreen />} />
        <Route path="/scan/:kind" element={<Scan />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </NoticeGate>
  );
}

export function App() {
  return (
    <SessionProvider>
      <Gate />
    </SessionProvider>
  );
}
