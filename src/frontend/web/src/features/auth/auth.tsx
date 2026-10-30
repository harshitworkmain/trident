import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { api, hasRefreshToken, onAuthChange, refreshSession } from '../../api/client';
import { startLive, stopLive } from '../../api/live';
import type { Role, User } from '../../api/types';
import { can as canDo, type Action } from '../../lib/permissions';
import type { SosRecord } from '../../api/types';

type Status = 'checking' | 'anon' | 'authed';

interface AuthCtx {
  user: User | null;
  status: Status;
  login: (u: string, p: string) => Promise<User>;
  logout: () => Promise<void>;
  can: (a: Action, sos?: Pick<SosRecord, 'assigned_team'>) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<Status>(() => (hasRefreshToken() ? 'checking' : 'anon'));

  useEffect(() => onAuthChange((u) => {
    setUser(u);
    setStatus(u ? 'authed' : 'anon');
  }), []);

  // Restore a session from the stored refresh token on first load.
  useEffect(() => {
    if (status !== 'checking') return;
    void refreshSession().then((ok) => { if (!ok) setStatus('anon'); });
  }, [status]);

  useEffect(() => {
    if (status === 'authed') startLive();
    else if (status === 'anon') stopLive();
  }, [status]);

  const login = useCallback((u: string, p: string) => api.login(u, p), []);
  const logout = useCallback(() => api.logout(), []);
  const can = useCallback((a: Action, sos?: Pick<SosRecord, 'assigned_team'>) => canDo(user, a, sos), [user]);

  const value = useMemo(() => ({ user, status, login, logout, can }), [user, status, login, logout, can]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth outside AuthProvider');
  return c;
}

export function RequireAuth({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { status, user } = useAuth();
  const loc = useLocation();
  if (status === 'checking') return <div className="boot" aria-busy="true"><span className="skeleton" style={{ width: 160 }} /></div>;
  if (status === 'anon' || !user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="page"><div className="state-block state-block--error" role="alert">
        <strong>Not available for your role</strong>
        <span>This page needs one of: {roles.join(', ')}. You are signed in as {user.role}.</span>
      </div></div>
    );
  }
  return <>{children}</>;
}
