import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { ApiError, onApiError } from '../api/client';

export interface ToastInput {
  tone?: 'info' | 'ok' | 'warning' | 'critical';
  title: string;
  message?: string;
  requestId?: string | null;
  ttl?: number;
}
interface ToastItem extends ToastInput { id: number }

const Ctx = createContext<(t: ToastInput) => void>(() => {});
export const useToast = () => useContext(Ctx);

/** Shorthand for surfacing a failed action. 5xx are already toasted globally by the client. */
export function useErrorToast() {
  const push = useToast();
  return useCallback((e: unknown, title = 'Action failed') => {
    if (e instanceof ApiError && e.isServer) return;
    const err = e instanceof ApiError ? e : null;
    push({ tone: 'critical', title, message: err?.message ?? (e as Error)?.message ?? 'Unknown error', requestId: err?.requestId });
  }, [push]);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const push = useCallback((t: ToastInput) => {
    const id = nextId.current++;
    setItems((xs) => [...xs.slice(-3), { ...t, id }]);
    window.setTimeout(() => dismiss(id), t.ttl ?? (t.tone === 'critical' ? 9000 : 5000));
  }, [dismiss]);

  useEffect(() => onApiError((e) => push({
    tone: 'critical', title: e.status === 503 ? 'Service unavailable' : 'Server error', message: e.message, requestId: e.requestId,
  })), [push]);

  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toast-region" role="region" aria-label="Notifications">
        <div aria-live="polite" style={{ display: 'contents' }}>
          {items.map((t) => (
            <div key={t.id} className={`toast toast--${t.tone ?? 'info'}`} role={t.tone === 'critical' ? 'alert' : 'status'}>
              <div>
                <div className="toast-title">{t.title}</div>
                {t.message && <div className="toast-msg">{t.message}</div>}
                {t.requestId && <div className="toast-meta mono">request {t.requestId}</div>}
              </div>
              <button className="btn btn--ghost btn--icon btn--sm" aria-label="Dismiss" onClick={() => dismiss(t.id)}><X /></button>
            </div>
          ))}
        </div>
      </div>
    </Ctx.Provider>
  );
}
