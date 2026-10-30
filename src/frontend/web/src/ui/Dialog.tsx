import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { Button } from './primitives';

/** Native <dialog>: focus trapping, Esc and inert background come from the platform. */
export function Dialog({ open, onClose, title, children, footer, wide, labelledBy }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean; labelledBy?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<Element | null>(null);
  const titleId = labelledBy ?? 'dlg-title';

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement;
      d.showModal();
    } else if (!open && d.open) {
      d.close();
    }
  }, [open]);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    const onCancel = (e: Event) => { e.preventDefault(); onClose(); };
    const onClosed = () => { (opener.current as HTMLElement | null)?.focus?.(); };
    d.addEventListener('cancel', onCancel);
    d.addEventListener('close', onClosed);
    return () => { d.removeEventListener('cancel', onCancel); d.removeEventListener('close', onClosed); };
  }, [onClose]);

  return (
    <dialog ref={ref} className={`dialog ${wide ? 'dialog--wide' : ''}`} aria-labelledby={titleId}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      {open && (
        <>
          <div className="dialog-head">
            <h2 id={titleId}>{title}</h2>
            <Button variant="ghost" iconOnly size="sm" aria-label="Close" onClick={onClose} style={{ marginLeft: 'auto' }} icon={<X />} />
          </div>
          <div className="dialog-body">{children}</div>
          {footer && <div className="dialog-foot">{footer}</div>}
        </>
      )}
    </dialog>
  );
}

/** Confirmation for consequential actions (ROV deploy, cancelling an SOS, key rotation). */
export function ConfirmDialog({ open, title, body, confirmLabel, danger, busy, onConfirm, onClose }: {
  open: boolean; title: string; body: ReactNode; confirmLabel: string; danger?: boolean; busy?: boolean;
  onConfirm: () => void; onClose: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title} labelledBy="confirm-title"
      footer={(
        <>
          <Button onClick={onClose}>Back</Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={onConfirm} busy={busy} autoFocus>{confirmLabel}</Button>
        </>
      )}>
      {body}
    </Dialog>
  );
}
