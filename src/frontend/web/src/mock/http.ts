export class HttpError extends Error {
  constructor(public status: number, public code: string, msg: string, public details?: unknown) {
    super(msg);
  }
}

type Emit = (topic: 'sos' | 'alerts' | 'devices' | 'weather' | 'rov' | 'system', data: unknown) => void;
let emitter: Emit = () => {};
export const setEmitter = (e: Emit) => { emitter = e; };
export const emit: Emit = (t, d) => emitter(t, d);

// ─── Audit log (GET /audit), newest first ───
export interface MockAudit { id: number; actor: string | null; action: string; target: string | null; details: Record<string, unknown> | null; request_id: string | null; at: string }
export const auditLog: MockAudit[] = [];
let auditId = 0;
export function audit(actor: string | null, action: string, target: string | null, details: Record<string, unknown> | null = null, atMs = Date.now()) {
  auditLog.unshift({ id: ++auditId, actor, action, target, details, request_id: `req_${Math.floor(Math.random() * 1e9).toString(36)}`, at: new Date(atMs).toISOString() });
}
