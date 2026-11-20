import { useI18n } from '@oglos/i18n';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Approvals } from './screens/Approvals';
import { Attendance, EntranceQr, Flags } from './screens/Live';
import { EnrolTotp, Login } from './screens/Login';
import { DesksScreen, RosterScreen, StaffScreen, TemplatesScreen } from './screens/Setup';
import { Today } from './screens/Today';
import { SessionProvider, useSession } from './session';

function Gate() {
  const { me, ready } = useSession();
  const { t } = useI18n();
  if (!ready)
    return (
      <div className="grid min-h-screen place-items-center text-ink2">{t('common.loading')}</div>
    );
  if (!me) return <Login />;
  if (me.mfa_pending) return <EnrolTotp />;
  return (
    <Routes>
      <Route path="/" element={<Today />} />
      <Route path="/approvals" element={<Approvals />} />
      <Route path="/flags" element={<Flags />} />
      <Route path="/attendance" element={<Attendance />} />
      <Route path="/entrance-qr" element={<EntranceQr />} />
      <Route path="/staff" element={<StaffScreen />} />
      <Route path="/desks" element={<DesksScreen />} />
      <Route path="/roster" element={<RosterScreen />} />
      <Route path="/templates" element={<TemplatesScreen />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function App() {
  return (
    <SessionProvider>
      <Gate />
    </SessionProvider>
  );
}
