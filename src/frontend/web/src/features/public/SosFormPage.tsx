import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronLeft, ChevronRight, Copy, Crosshair, MessageSquare, Minus, Plus, RefreshCw } from 'lucide-react';
import { api, ApiError } from '../../api/client';
import { EMERGENCY_TYPES, type EmergencyType, type SosSubmit, type SosSubmitResponse, type SupplyLevel, type Vulnerabilities } from '../../api/types';
import { useLocalStorage } from '../../lib/hooks';
import { hhmm, uuid } from '../../lib/format';
import { ScrambleText } from '../../ui/effects';
import { composeSms, discard, enqueue, flushOutbox, isRetryable, smsHref, useOutbox, useSmsNumber, type OutboxItem } from './offline';
import { EmergencyNumbers, PublicFooter, PublicHeader } from './PublicChrome';

interface Draft {
  emergency_type: EmergencyType | '';
  latitude: number | null;
  longitude: number | null;
  accuracy_m: number | null;
  address: string;
  city: string;
  pincode: string;
  people_to_rescue: number;
  people_injured: number;
  vulnerabilities: Vulnerabilities;
  food_availability: SupplyLevel | '';
  water_availability: SupplyLevel | '';
  additional_info: string;
  name: string;
  age: string;
  phone: string;
  email: string;
  device_id: string;
  idempotency_key: string;
}

const EMPTY: Draft = {
  emergency_type: '', latitude: null, longitude: null, accuracy_m: null, address: '', city: 'Chennai', pincode: '',
  people_to_rescue: 1, people_injured: 0,
  vulnerabilities: { pregnant: false, elderly: false, children: false, disabled: false, medical: false },
  food_availability: '', water_availability: '', additional_info: '', name: '', age: '', phone: '', email: '', device_id: '',
  idempotency_key: '',
};

const TYPE_LABEL: Record<EmergencyType, [string, string]> = {
  flood: ['Flooding', 'Water inside or around the building'],
  'water-level-rising': ['Water rising', 'Not flooded yet, but rising fast'],
  medical: ['Medical', 'Someone needs a doctor urgently'],
  storm: ['Storm damage', 'Collapsed roof, wall or tree'],
  'dam-breach': ['Dam or lake breach', 'Sudden surge from a lake or reservoir'],
  tsunami: ['Tsunami', 'Coastal surge after an earthquake'],
  'coastal-erosion': ['Coastal erosion', 'House at the shore is unsafe'],
  other: ['Something else', 'Describe it in the last step'],
};

const VUL_LABEL: Record<keyof Vulnerabilities, string> = {
  elderly: 'Elderly person (65+)', children: 'Children under 12', pregnant: 'Pregnant woman',
  disabled: 'Cannot walk or climb', medical: 'Needs medicine, oxygen or dialysis',
};

const SUPPLY: [SupplyLevel, string][] = [['adequate', 'Enough for 2+ days'], ['limited', 'About a day'], ['critical', 'A few hours'], ['none', 'None left']];

const STEPS = ['What and where', 'Who is there', 'Food and water', 'Your contact'];

function Stepper({ label, value, onChange, min = 0, max = 200 }: { label: string; value: number; onChange: (n: number) => void; min?: number; max?: number }) {
  const id = label.replace(/\W+/g, '-').toLowerCase();
  return (
    <div className="counter">
      <label htmlFor={id} className="field-label">{label}</label>
      <div className="counter-ctrl">
        <button type="button" className="btn btn--lg btn--icon" aria-label={`Fewer: ${label}`} onClick={() => onChange(Math.max(min, value - 1))} disabled={value <= min}><Minus /></button>
        <input id={id} className="input input--lg mono" inputMode="numeric" value={value}
          onChange={(e) => { const n = parseInt(e.target.value.replace(/\D/g, ''), 10); onChange(Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : min); }} />
        <button type="button" className="btn btn--lg btn--icon" aria-label={`More: ${label}`} onClick={() => onChange(Math.min(max, value + 1))}><Plus /></button>
      </div>
    </div>
  );
}

function Fieldset({ legend, children, hint }: { legend: string; children: ReactNode; hint?: string }) {
  return (
    <fieldset className="fieldset">
      <legend className="field-label">{legend}</legend>
      {hint && <p className="field-hint">{hint}</p>}
      {children}
    </fieldset>
  );
}

type Errors = Partial<Record<keyof Draft, string>>;

function validate(d: Draft, step: number): Errors {
  const e: Errors = {};
  if (step === 0) {
    if (!d.emergency_type) e.emergency_type = 'Choose what is happening.';
    if (!d.address.trim() && d.latitude === null) e.address = 'Share your location or type an address.';
    // Pincode is optional (someone in distress may not know it); when given it must look like one.
    const pin = d.pincode.trim();
    if (pin && (pin.length < 3 || pin.length > 12)) e.pincode = 'Check the pincode, or leave it empty.';
  }
  if (step === 1 && d.people_injured > d.people_to_rescue) e.people_injured = 'Injured cannot be more than the number of people.';
  if (step === 3) {
    if (!d.name.trim()) e.name = 'Enter a name the team can ask for.';
    if (!/^(\+?91)?[6-9]\d{9}$/.test(d.phone.replace(/[\s-]/g, ''))) e.phone = 'Enter a 10-digit mobile number.';
    if (d.age && (!/^\d{1,3}$/.test(d.age) || Number(d.age) > 120)) e.age = 'Enter an age in years (0 to 120), or leave it empty.';
    if (d.email && !/^\S+@\S+\.\S+$/.test(d.email)) e.email = 'Check the email address.';
  }
  return e;
}

/** Maps a 422 `validation_error` (details: [{loc: ['body', field], msg}]) onto the form's fields. */
function serverFieldErrors(err: ApiError): Errors {
  const list = Array.isArray(err.details) ? (err.details as { loc?: unknown[]; msg?: string }[]) : [];
  const e: Errors = {};
  for (const d of list) {
    const f = d.loc?.[1];
    if (typeof f === 'string' && f in EMPTY) e[f as keyof Draft] = d.msg ?? 'Check this answer.';
  }
  return e;
}

function toPayload(d: Draft): SosSubmit {
  return {
    name: d.name.trim(),
    age: d.age ? Number(d.age) : null,
    phone: d.phone.replace(/[\s-]/g, ''),
    email: d.email.trim() || undefined,
    address: d.address.trim() || (d.latitude !== null ? `GPS ${d.latitude.toFixed(5)}, ${d.longitude?.toFixed(5)}` : ''),
    city: d.city.trim() || 'Chennai',
    pincode: d.pincode.trim() || null,
    people_to_rescue: d.people_to_rescue,
    people_injured: d.people_injured,
    food_availability: d.food_availability || 'limited',
    water_availability: d.water_availability || 'limited',
    vulnerabilities: d.vulnerabilities,
    emergency_type: d.emergency_type || 'other',
    additional_info: d.additional_info.trim() || undefined,
    latitude: d.latitude ?? undefined,
    longitude: d.longitude ?? undefined,
    device_id: d.device_id.trim() || undefined,
  };
}

/** Back from a refused outbox item to an editable draft (a fresh Idempotency-Key is issued on send). */
function fromPayload(p: SosSubmit): Draft {
  return {
    ...EMPTY,
    emergency_type: p.emergency_type, latitude: p.latitude ?? null, longitude: p.longitude ?? null,
    address: p.address.startsWith('GPS ') ? '' : p.address, city: p.city, pincode: p.pincode ?? '',
    people_to_rescue: p.people_to_rescue, people_injured: p.people_injured, vulnerabilities: p.vulnerabilities,
    food_availability: p.food_availability, water_availability: p.water_availability, additional_info: p.additional_info ?? '',
    name: p.name, age: p.age == null ? '' : String(p.age), phone: p.phone, email: p.email ?? '', device_id: p.device_id ?? '',
  };
}

export function SosFormPage() {
  const [draft, setDraft, clearDraft] = useLocalStorage<Draft>('trident.sos.draft', EMPTY);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Errors>({});
  const [geo, setGeo] = useState<'idle' | 'locating' | 'denied' | 'unavailable'>('idle');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<ApiError | null>(null);
  const [done, setDone] = useState<SosSubmitResponse | null>(null);
  const outbox = useOutbox();
  useSmsNumber(); // caches the SMS fallback number while there is still a connection
  // The outbox item this page is waiting on (the newest one if the page was reopened).
  const [watchKey, setWatchKey] = useState<string | null>(() => outbox.items[outbox.items.length - 1]?.key ?? null);
  const [composeNew, setComposeNew] = useState(false);
  const queued = watchKey ? outbox.items.find((i) => i.key === watchKey) : undefined;
  const sentLater = watchKey ? outbox.sent[watchKey] : undefined;
  useEffect(() => {
    if (sentLater) { setDone(sentLater); setWatchKey(null); }
  }, [sentLater]);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const hasDraft = useRef(JSON.stringify({ ...draft, idempotency_key: '' }) !== JSON.stringify(EMPTY));

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => {
    setDraft((d) => ({ ...d, [k]: v }));
    if (errors[k]) setErrors((e) => ({ ...e, [k]: undefined }));
  };

  useEffect(() => { headingRef.current?.focus(); }, [step, done]);

  const locate = () => {
    if (!('geolocation' in navigator)) { setGeo('unavailable'); return; }
    setGeo('locating');
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setDraft((d) => ({ ...d, latitude: +p.coords.latitude.toFixed(6), longitude: +p.coords.longitude.toFixed(6), accuracy_m: Math.round(p.coords.accuracy) }));
        setErrors((e) => ({ ...e, address: undefined }));
        setGeo('idle');
      },
      (err) => setGeo(err.code === err.PERMISSION_DENIED ? 'denied' : 'unavailable'),
      { enableHighAccuracy: true, timeout: 15_000, maximumAge: 60_000 },
    );
  };

  const next = () => {
    const e = validate(draft, step);
    setErrors(e);
    if (Object.values(e).some(Boolean)) {
      const first = Object.keys(e)[0];
      document.getElementById(`f-${first}`)?.focus();
      return;
    }
    setStep((s) => Math.min(STEPS.length - 1, s + 1));
  };

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    if (step < STEPS.length - 1) { next(); return; }
    const e = { ...validate(draft, 0), ...validate(draft, 3) };
    setErrors(e);
    if (Object.values(e).some(Boolean)) {
      if (e.emergency_type || e.address || e.pincode) setStep(0);
      return;
    }
    // One key per draft: a retry after a timeout returns the original SOS instead of creating a second one.
    const key = draft.idempotency_key || uuid();
    if (!draft.idempotency_key) setDraft((d) => ({ ...d, idempotency_key: key }));
    const payload = toPayload(draft);
    // No connection, or it drops mid-send: keep the request on the phone (same key) and keep trying.
    const queue = () => {
      enqueue(key, payload);
      setWatchKey(key);
      setComposeNew(false);
      setDraft(EMPTY);
      hasDraft.current = false;
      setStep(0);
    };
    if (!navigator.onLine) { queue(); return; }
    setSending(true);
    setSendError(null);
    try {
      const res = await api.submitSos(payload, key);
      try { localStorage.setItem('trident.sos.last', JSON.stringify({ ref: res.reference_id, token: res.tracking_token })); } catch { /* ignore */ }
      clearDraft();
      setDone(res);
    } catch (err) {
      if (isRetryable(err)) queue();
      else {
        const ae = err instanceof ApiError ? err : new ApiError(0, 'network', 'Could not send.', null);
        const fe = serverFieldErrors(ae);
        if (Object.keys(fe).length) {
          setErrors(fe);
          if (fe.emergency_type || fe.address || fe.pincode || fe.city) setStep(0);
        }
        setSendError(ae);
      }
    } finally {
      setSending(false);
    }
  };

  if (done) return <Confirmation res={done} />;
  if (queued && !composeNew) {
    return (
      <Queued item={queued} sending={outbox.sending} online={outbox.online}
        onNew={() => setComposeNew(true)}
        onEdit={() => { setDraft(fromPayload(queued.payload)); discard(queued.key); setWatchKey(null); setStep(3); }} />
    );
  }

  const err = (k: keyof Draft) => errors[k] ? <p className="field-error" id={`e-${k}`} role="alert">{errors[k]}</p> : null;
  const inv = (k: keyof Draft) => ({ 'aria-invalid': !!errors[k] || undefined, 'aria-describedby': errors[k] ? `e-${k}` : undefined });

  return (
    <div className="public public--form">
      <PublicHeader right={<a href="tel:112" className="link-sweep">Call 112</a>} />
      <main id="main" className="sos-page">
        <div className="sos-main">
          <div className="sos-progress" aria-label={`Step ${step + 1} of ${STEPS.length}`}>
            {STEPS.map((s, i) => (
              <button key={s} type="button" className={`sos-step ${i === step ? 'is-current' : ''} ${i < step ? 'is-done' : ''}`}
                onClick={() => i < step && setStep(i)} disabled={i > step} aria-current={i === step ? 'step' : undefined}>
                <span className="mono">{i < step ? <Check aria-hidden="true" /> : i + 1}</span>
                <span className="sos-step-label">{s}</span>
              </button>
            ))}
          </div>

          {hasDraft.current && step === 0 && (
            <p className="banner banner--info" role="status">Your earlier answers were restored from this device.
              <button type="button" className="btn btn--sm btn--ghost" onClick={() => { setDraft(EMPTY); hasDraft.current = false; }}>Start over</button>
            </p>
          )}

          <form onSubmit={submit} noValidate className="sos-form">
            <h1 ref={headingRef} tabIndex={-1} className="sos-title">{STEPS[step]}</h1>

            {step === 0 && (
              <>
                <Fieldset legend="What is happening?">
                  <div className="tile-grid" role="radiogroup" aria-describedby={errors.emergency_type ? 'e-emergency_type' : undefined} id="f-emergency_type" tabIndex={-1}>
                    {EMERGENCY_TYPES.map((t) => (
                      <label key={t} className={`tile ${draft.emergency_type === t ? 'is-on' : ''}`}>
                        <input type="radio" name="etype" value={t} checked={draft.emergency_type === t} onChange={() => set('emergency_type', t)} />
                        <span className="tile-title">{TYPE_LABEL[t][0]}</span>
                        <span className="tile-sub">{TYPE_LABEL[t][1]}</span>
                      </label>
                    ))}
                  </div>
                  {err('emergency_type')}
                </Fieldset>

                <Fieldset legend="Where are you?" hint="Your phone's location is the fastest way for a boat to find you. Add a landmark below if you can.">
                  <div className="geo-row">
                    <button type="button" className="btn btn--lg" onClick={locate} disabled={geo === 'locating'}>
                      <Crosshair aria-hidden="true" />{geo === 'locating' ? 'Finding you…' : draft.latitude !== null ? 'Update my location' : 'Use my location'}
                    </button>
                    <div className="geo-status" role="status">
                      {draft.latitude !== null && <span className="mono">{draft.latitude.toFixed(5)}, {draft.longitude?.toFixed(5)}{draft.accuracy_m ? ` · ±${draft.accuracy_m} m` : ''}</span>}
                      {geo === 'denied' && <span className="field-error">Location permission was refused. Type your address instead.</span>}
                      {geo === 'unavailable' && <span className="field-error">Location is not available on this device. Type your address instead.</span>}
                    </div>
                  </div>
                  <label className="field">
                    <span className="field-label">Address and landmark</span>
                    <textarea id="f-address" className="textarea textarea--lg" rows={2} value={draft.address} placeholder="Door no., street, area. e.g. 14, 2nd Cross St, Velachery, behind the bus depot"
                      onChange={(e) => set('address', e.target.value)} {...inv('address')} autoComplete="street-address" />
                    {err('address')}
                  </label>
                  <div className="row-2">
                    <label className="field">
                      <span className="field-label">Area / city</span>
                      <input className="input input--lg" value={draft.city} onChange={(e) => set('city', e.target.value)} autoComplete="address-level2" />
                    </label>
                    <label className="field">
                      <span className="field-label">Pincode <span className="muted">(optional)</span></span>
                      <input id="f-pincode" className="input input--lg mono" inputMode="numeric" maxLength={12} value={draft.pincode}
                        onChange={(e) => set('pincode', e.target.value.replace(/[^\dA-Za-z -]/g, ''))} {...inv('pincode')} autoComplete="postal-code" />
                      {err('pincode')}
                    </label>
                  </div>
                </Fieldset>
              </>
            )}

            {step === 1 && (
              <>
                <div className="row-2">
                  <Stepper label="People who need rescue" value={draft.people_to_rescue} min={1} onChange={(n) => set('people_to_rescue', n)} />
                  <div>
                    <Stepper label="Of them, injured" value={draft.people_injured} onChange={(n) => set('people_injured', n)} max={draft.people_to_rescue} />
                    {err('people_injured')}
                  </div>
                </div>
                <Fieldset legend="Is anyone in these groups?" hint="Tick all that apply. These raise the priority of your request.">
                  <div className="check-list">
                    {(Object.keys(VUL_LABEL) as (keyof Vulnerabilities)[]).map((k) => (
                      <label key={k} className={`check ${draft.vulnerabilities[k] ? 'is-on' : ''}`}>
                        <input type="checkbox" checked={draft.vulnerabilities[k]} onChange={(e) => set('vulnerabilities', { ...draft.vulnerabilities, [k]: e.target.checked })} />
                        <span>{VUL_LABEL[k]}</span>
                      </label>
                    ))}
                  </div>
                </Fieldset>
              </>
            )}

            {step === 2 && (
              <>
                {(['water_availability', 'food_availability'] as const).map((k) => (
                  <Fieldset key={k} legend={k === 'water_availability' ? 'Drinking water left' : 'Food left'}>
                    <div className="seg-lg" role="radiogroup">
                      {SUPPLY.map(([v, label]) => (
                        <label key={v} className={`seg-opt ${draft[k] === v ? 'is-on' : ''} ${v === 'none' || v === 'critical' ? 'seg-opt--warn' : ''}`}>
                          <input type="radio" name={k} value={v} checked={draft[k] === v} onChange={() => set(k, v)} />
                          <span>{label}</span>
                        </label>
                      ))}
                    </div>
                  </Fieldset>
                ))}
                <label className="field">
                  <span className="field-label">Anything else the team should know <span className="muted">(optional)</span></span>
                  <textarea className="textarea textarea--lg" rows={3} value={draft.additional_info} onChange={(e) => set('additional_info', e.target.value)}
                    placeholder="Which floor you are on, how to reach the building, pets, medicines needed…" maxLength={1000} />
                </label>
              </>
            )}

            {step === 3 && (
              <>
                <div className="row-2">
                  <label className="field">
                    <span className="field-label">Name</span>
                    <input id="f-name" className="input input--lg" value={draft.name} onChange={(e) => set('name', e.target.value)} autoComplete="name" {...inv('name')} />
                    {err('name')}
                  </label>
                  <label className="field">
                    <span className="field-label">Age <span className="muted">(optional)</span></span>
                    <input id="f-age" className="input input--lg mono" inputMode="numeric" maxLength={3} value={draft.age} onChange={(e) => set('age', e.target.value.replace(/\D/g, ''))} {...inv('age')} />
                    {err('age')}
                  </label>
                </div>
                <label className="field">
                  <span className="field-label">Mobile number</span>
                  <input id="f-phone" className="input input--lg mono" type="tel" inputMode="tel" value={draft.phone} placeholder="98xxxxxxxx" onChange={(e) => set('phone', e.target.value)} autoComplete="tel" {...inv('phone')} />
                  <span className="field-hint">The rescue team will call this number. Keep the phone on.</span>
                  {err('phone')}
                </label>
                <label className="field">
                  <span className="field-label">Email <span className="muted">(optional)</span></span>
                  <input id="f-email" className="input input--lg" type="email" value={draft.email} onChange={(e) => set('email', e.target.value)} autoComplete="email" {...inv('email')} />
                  {err('email')}
                </label>
                <label className="field">
                  <span className="field-label">TRIDENT band ID <span className="muted">(only if you were given a wristband)</span></span>
                  <input className="input input--lg mono" value={draft.device_id} placeholder="TRD-W00" onChange={(e) => set('device_id', e.target.value.toUpperCase())} />
                </label>
                <Summary d={draft} />
                {!outbox.online && (
                  <p className="banner banner--warning" role="status">
                    <span><strong>No connection right now.</strong> Press Send anyway: the request is saved on this phone and sent automatically when a connection returns.</span>
                  </p>
                )}
                {!outbox.online && draft.emergency_type && <SmsFallback payload={toPayload(draft)} />}
                {sendError && (
                  <div className="banner banner--critical" role="alert">
                    <div>
                      <strong>{sendError.status === 0 ? 'Not sent: no connection.' : sendError.status === 429 ? 'Too many requests from this network.' : 'Not sent.'}</strong>{' '}
                      {sendError.status === 0 ? 'Your answers are saved on this phone. Move to better signal and press Send again; it will not create a duplicate.' : sendError.message}
                      {sendError.requestId && <span className="mono muted"> · {sendError.requestId}</span>}
                    </div>
                  </div>
                )}
              </>
            )}

            <div className="sos-nav">
              {step > 0 && <button type="button" className="btn btn--lg" onClick={() => setStep(step - 1)}><ChevronLeft aria-hidden="true" />Back</button>}
              {step < STEPS.length - 1
                ? <button type="submit" className="btn btn--lg btn--primary">Next<ChevronRight aria-hidden="true" /></button>
                : <button type="submit" className="btn btn--lg btn--primary" disabled={sending} aria-busy={sending}>{sending ? 'Sending…' : 'Send request for help'}</button>}
            </div>
            <p className="field-hint saved-note">Saved on this phone as you type.</p>
          </form>
        </div>
        <EmergencyNumbers compact />
      </main>
      <PublicFooter />
    </div>
  );
}

function Summary({ d }: { d: Draft }) {
  const vul = (Object.keys(VUL_LABEL) as (keyof Vulnerabilities)[]).filter((k) => d.vulnerabilities[k]).map((k) => VUL_LABEL[k].toLowerCase());
  return (
    <section className="sos-summary" aria-label="Check before sending">
      <h2>Check before sending</h2>
      <dl className="kv">
        <dt>Emergency</dt><dd>{d.emergency_type ? TYPE_LABEL[d.emergency_type][0] : '—'}</dd>
        <dt>Location</dt><dd>{d.address || (d.latitude !== null ? <span className="mono">{d.latitude}, {d.longitude}</span> : '—')}</dd>
        <dt>People</dt><dd>{d.people_to_rescue}{d.people_injured ? `, ${d.people_injured} injured` : ''}</dd>
        {vul.length > 0 && <><dt>Includes</dt><dd>{vul.join(', ')}</dd></>}
        <dt>Water / food</dt><dd>{d.water_availability || 'not given'} / {d.food_availability || 'not given'}</dd>
      </dl>
    </section>
  );
}

function Confirmation({ res }: { res: SosSubmitResponse }) {
  const link = `${location.origin}/track/${encodeURIComponent(res.reference_id)}?token=${encodeURIComponent(res.tracking_token)}`;
  const [copied, setCopied] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { titleRef.current?.focus(); }, []);
  const copy = async () => {
    try { await navigator.clipboard.writeText(link); setCopied(true); window.setTimeout(() => setCopied(false), 2000); } catch { /* user can select the text */ }
  };
  return (
    <div className="public public--form">
      <PublicHeader />
      <main id="main" className="confirm">
        <p className="eyebrow mono">Request received</p>
        <h1 ref={titleRef} tabIndex={-1}>Help has been requested.</h1>
        <div className="ref-block" aria-live="polite">
          <span className="field-label">Your reference</span>
          <ScrambleText text={res.reference_id} className="ref-id" onMount />
          <span className="muted">Write this down or take a screenshot. Give it to the rescue team or the 1070 helpline if they ask.</span>
        </div>
        <div className="track-link">
          <span className="field-label">Tracking link</span>
          <div className="track-link-row">
            <code className="mono">{link}</code>
            <button type="button" className="btn" onClick={copy}>{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}{copied ? 'Copied' : 'Copy'}</button>
          </div>
          <Link to={`/track/${encodeURIComponent(res.reference_id)}?token=${encodeURIComponent(res.tracking_token)}`} className="btn btn--primary btn--lg">Open tracking page</Link>
        </div>
        <section className="next-steps" aria-labelledby="next-title">
          <h2 id="next-title">What happens next</h2>
          <ol>
            <li>The control room sees your request now. It is ranked priority <strong className="mono">P{res.priority}</strong> of 5 (P1 is most urgent) and a dispatcher will check it.</li>
            <li>A rescue team with space will be assigned. The tracking page shows when they are on the way.</li>
            <li>Stay where you said you are. Keep your phone on and charged; the team may call you.</li>
            <li>If the situation gets worse, send a new request or call 112.</li>
          </ol>
        </section>
        <EmergencyNumbers compact />
      </main>
      <PublicFooter />
    </div>
  );
}

function Queued({ item, sending, online, onNew, onEdit }: {
  item: OutboxItem; sending: boolean; online: boolean; onNew: () => void; onEdit: () => void;
}) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => { titleRef.current?.focus(); }, []);
  const rejected = item.rejected;
  const status = sending ? 'Sending now…'
    : !online ? 'This phone is offline. Waiting for a connection.'
      : item.attempts ? `Not through yet. Last try ${hhmm(item.last_try)}; trying again every 30 seconds.` : 'Waiting to send.';
  return (
    <div className="public public--form">
      <PublicHeader right={<a href="tel:112" className="link-sweep">Call 112</a>} />
      <main id="main" className="confirm">
        <p className="eyebrow mono">Not sent yet</p>
        <h1 ref={titleRef} tabIndex={-1}>{rejected ? 'The request was not accepted.' : 'Saved on this phone.'}</h1>
        {rejected ? (
          <div className="banner banner--critical" role="alert">
            <div>
              <strong>The server refused it:</strong> {rejected.message}
              {rejected.request_id && <span className="mono muted"> · {rejected.request_id}</span>}
            </div>
            <button type="button" className="btn" onClick={onEdit}>Edit and send again</button>
          </div>
        ) : (
          <div className="queued-block">
            <p className="queued-lede">It will be sent automatically when a connection returns — keep this page open if you can.</p>
            <p className="queued-status" role="status" aria-live="polite">
              <span className={`dot ${online ? 'dot--warning' : 'dot--critical'}`} aria-hidden="true" />
              {status}
            </p>
            <div className="action-row">
              <button type="button" className="btn btn--lg" onClick={() => void flushOutbox()} disabled={sending} aria-busy={sending}>
                <RefreshCw aria-hidden="true" />Try now
              </button>
              <button type="button" className="btn btn--lg btn--ghost" onClick={onNew}>Send another request</button>
            </div>
            <p className="field-hint">Saved at {hhmm(item.queued_at)}. Sending it more than once is safe: it is only counted once.</p>
          </div>
        )}
        <SmsFallback payload={item.payload} />
        <EmergencyNumbers compact />
      </main>
      <PublicFooter />
    </div>
  );
}

/** "Send by SMS instead": opens the messages app with the compact format the server parses. */
function SmsFallback({ payload }: { payload: SosSubmit }) {
  const number = useSmsNumber();
  const [copied, setCopied] = useState(false);
  if (!number) return null;
  const text = composeSms(payload);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 2000); } catch { /* user can select the text */ }
  };
  return (
    <section className="sms-fallback" aria-labelledby="sms-title">
      <h2 id="sms-title">Send by SMS instead</h2>
      <p>An SMS often gets through when mobile data does not. This opens your messages app with the text below, addressed to <span className="mono">{number}</span>.</p>
      <a className="btn btn--lg btn--primary" href={smsHref(number, text)}><MessageSquare aria-hidden="true" />Send by SMS</a>
      <div className="track-link-row">
        <code className="mono" aria-label="SMS text">{text}</code>
        <button type="button" className="btn" onClick={copy}>{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}{copied ? 'Copied' : 'Copy'}</button>
      </div>
      <span className="field-hint">If the button does not open your messages, send exactly this text to <span className="mono">{number}</span> (<span className="mono">{text.length}</span>/160 characters).</span>
    </section>
  );
}
