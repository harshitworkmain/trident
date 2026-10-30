import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../../api/client';
import { Button } from '../../ui/primitives';
import { useAuth } from './auth';

export function LoginPage() {
  const { login, status } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from ?? '/ops';
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === 'authed') return <Navigate to={from} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      nav(from, { replace: true });
    } catch (err) {
      const ae = err instanceof ApiError ? err : null;
      setError(ae?.status === 401 ? 'Wrong username or password.' : ae?.status === 429 ? 'Too many attempts. Wait a minute and try again.' : ae?.message ?? 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main id="main" className="login">
      <div className="login-card">
        <Link to="/" className="brand brand--lg"><img src="/logo.png" alt="" width={32} height={32} /><span>TRIDENT</span></Link>
        <h1>Staff sign-in</h1>
        <p className="muted">Control room, dispatch and field teams. Members of the public do not need an account: <Link to="/sos">request help here</Link>.</p>
        <form onSubmit={submit} className="stack" noValidate>
          <label className="field">
            <span className="field-label">Username</span>
            <input className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </label>
          <label className="field">
            <span className="field-label">Password</span>
            <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          {error && <p className="field-error" role="alert">{error}</p>}
          <Button type="submit" variant="primary" block busy={busy} disabled={!username || !password}>Sign in</Button>
        </form>
        {import.meta.env.VITE_MOCK === '1' && (
          <p className="login-hint mono">Mock mode: admin, dispatcher, responder or viewer / trident</p>
        )}
      </div>
    </main>
  );
}
