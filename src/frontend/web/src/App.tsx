import { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireAuth } from './features/auth/auth';
import { LoginPage } from './features/auth/LoginPage';
import { StaffLayout } from './features/shell/StaffLayout';
import { LandingPage } from './features/public/LandingPage';
import { SosFormPage } from './features/public/SosFormPage';
import { TrackPage } from './features/public/TrackPage';
import { ToastProvider } from './ui/Toast';
import { Skeleton } from './ui/primitives';

// Staff pages are split out so the public SOS form stays small on slow mobile connections.
const OpsPage = lazy(() => import('./features/ops/OpsPage'));
const SosDetailPage = lazy(() => import('./features/sos/SosDetailPage'));
const WearablesPage = lazy(() => import('./features/wearables/WearablesPage'));
const WearableDetailPage = lazy(() => import('./features/wearables/WearableDetailPage'));
const WeatherPage = lazy(() => import('./features/weather/WeatherPage'));
const AnalyticsPage = lazy(() => import('./features/analytics/AnalyticsPage'));
const RovPage = lazy(() => import('./features/rov/RovPage'));
const MissionsPage = lazy(() => import('./features/rov/MissionsPage'));
const AdminPage = lazy(() => import('./features/admin/AdminPage'));

function NotFound() {
  return (
    <div className="public-page narrow">
      <h1>Page not found</h1>
      <p className="muted">If you need help, <a href="/sos">send a request for rescue</a>.</p>
    </div>
  );
}

export default function App() {
  const lazyPage = (el: JSX.Element) => <Suspense fallback={<div className="page"><Skeleton rows={8} /></div>}>{el}</Suspense>;
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/sos" element={<SosFormPage />} />
            <Route path="/track/:ref" element={<TrackPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route element={<RequireAuth><StaffLayout /></RequireAuth>}>
              <Route path="/ops" element={lazyPage(<OpsPage />)} />
              <Route path="/sos/:ref" element={lazyPage(<SosDetailPage />)} />
              <Route path="/wearables" element={lazyPage(<WearablesPage />)} />
              <Route path="/wearables/:id" element={lazyPage(<WearableDetailPage />)} />
              <Route path="/weather" element={lazyPage(<WeatherPage />)} />
              <Route path="/analytics" element={lazyPage(<AnalyticsPage />)} />
              <Route path="/rov" element={lazyPage(<RovPage />)} />
              <Route path="/missions" element={lazyPage(<MissionsPage />)} />
              <Route path="/admin" element={<RequireAuth roles={['admin']}>{lazyPage(<AdminPage />)}</RequireAuth>} />
            </Route>
            <Route path="/dashboard" element={<Navigate to="/ops" replace />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
