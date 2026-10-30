import { useState, type ReactNode } from 'react';
import { Check, Copy } from 'lucide-react';
import { Dialog } from './Dialog';
import { Button } from './primitives';

/** A secret exists in plain text only in this dialog; the server stores its hash. Closing needs an explicit "stored it". */
export function KeyReveal({ title, apiKey, hint, onClose }: { title: string; apiKey: string; hint?: ReactNode; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const [ack, setAck] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
    } catch { /* the user can select the text */ }
  };
  return (
    <Dialog open onClose={() => { if (ack) onClose(); }} title={title} labelledBy="key-title"
      footer={<Button variant="primary" disabled={!ack} onClick={onClose}>Done</Button>}>
      <div className="banner banner--warning" role="alert">This key is shown once. It cannot be retrieved later; if it is lost, rotate it.</div>
      <div className="key-box">
        <code className="mono" aria-label="API key">{apiKey}</code>
        <Button size="sm" icon={copied ? <Check /> : <Copy />} onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
      </div>
      {hint && <div className="field-hint key-hint">{hint}</div>}
      <label className="check-inline"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I have stored this key</label>
    </Dialog>
  );
}
