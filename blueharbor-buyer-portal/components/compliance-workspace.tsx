'use client';

import { useMemo, useState, type CSSProperties, type SyntheticEvent } from 'react';
import {
  ArrowRight,
  Building2,
  Check,
  FileCheck2,
  FileText,
  Fingerprint,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { NativeSelect } from '@/components/ui/native-select';

type Buyer = {
  email: string;
  name: string;
  company: string;
  country: string;
  registration: string;
  address: string;
  phone: string;
  verified: string;
};

type Doc = {
  id: string;
  kind: string;
  name: string;
  expiry: string;
  size: number;
};

type Props = {
  user: Buyer;
  docs: Doc[];
  required: string[];
  countries: string[];
  busy: boolean;
  onSaveProfile: (data: Record<string, FormDataEntryValue>) => Promise<boolean>;
  onUpload: (file: File, kind: string, expiry: string) => Promise<boolean>;
  onSubmit: () => Promise<boolean>;
};

const stages = [
  { label: 'Account', icon: Fingerprint },
  { label: 'Company', icon: Building2 },
  { label: 'Documents', icon: FileText },
  { label: 'Review', icon: FileCheck2 },
  { label: 'Status', icon: ShieldCheck },
];

export default function ComplianceWorkspace({
  user,
  docs,
  required,
  countries,
  busy,
  onSaveProfile,
  onUpload,
  onSubmit,
}: Props) {
  const profileComplete = Boolean(
    user.name && user.company && user.registration && user.address && user.phone,
  );
  const validKinds = useMemo(
    () =>
      new Set(
        docs
          .filter((doc) => doc.expiry >= new Date().toISOString().slice(0, 10))
          .map((doc) => doc.kind),
      ),
    [docs],
  );
  const documentsComplete = required.length > 0 && required.every((kind) => validKinds.has(kind));
  const submitted = ['UNDER_REVIEW', 'VERIFIED'].includes(user.verified);
  const initial = submitted ? 4 : documentsComplete && profileComplete ? 3 : profileComplete ? 2 : 1;
  const [step, setStep] = useState(initial);
  const maxUnlocked = submitted ? 4 : documentsComplete && profileComplete ? 3 : profileComplete ? 2 : 1;
  const completed = [true, profileComplete, documentsComplete, submitted, user.verified === 'VERIFIED'];
  const progress = Math.round((completed.filter(Boolean).length / completed.length) * 100);

  return (
    <div className="compliance-shell">
      <section className="compliance-intro">
        <div>
          <p className="eyebrow">BUYER TRUST JOURNEY</p>
          <h1>Become ready to trade.</h1>
          <p>
            Complete each stage so our India export desk can confirm your business before stock can be reserved.
          </p>
        </div>
        <div
          className="compliance-score"
          style={{ '--progress': `${progress}%` } as CSSProperties}
          aria-label={`${progress}% complete`}
        >
          <span>{progress}%</span>
          <small>COMPLIANCE PROGRESS</small>
        </div>
      </section>

      <div className="compliance-layout">
        <nav className="compliance-steps" aria-label="Compliance stages">
          {stages.map(({ label, icon: Icon }, index) => (
            <button
              type="button"
              key={label}
              className={`${step === index ? 'active' : ''} ${completed[index] ? 'complete' : ''}`}
              disabled={index > maxUnlocked}
              onClick={() => setStep(index)}
            >
              <span>{completed[index] ? <Check size={17} /> : <Icon size={17} />}</span>
              <div><small>STEP {index + 1}</small><b>{label}</b></div>
            </button>
          ))}
        </nav>

        <section className="compliance-stage">
          {step === 0 && (
            <div className="stage-copy stage-account">
              <span className="stage-icon"><Fingerprint size={28} /></span>
              <p className="eyebrow">IDENTITY CONFIRMED</p>
              <h2>Your secure account is active.</h2>
              <p>Supabase has confirmed your email. We’ll use it for account access and important trade updates.</p>
              <div className="identity-card"><span>Email</span><b>{user.email}</b><i><Check size={14} /> Confirmed</i></div>
              <Button onClick={() => setStep(1)}>Continue to company details <ArrowRight size={16} /></Button>
            </div>
          )}

          {step === 1 && (
            <form
              className="stage-copy"
              onSubmit={async (event) => {
                event.preventDefault();
                const ok = await onSaveProfile(Object.fromEntries(new FormData(event.currentTarget)));
                if (ok) setStep(2);
              }}
            >
              <p className="eyebrow">COMPANY IDENTITY</p>
              <h2>Tell us who is trading.</h2>
              <p>Use the legal information shown on your registration documents.</p>
              <div className="guided-prompt"><Sparkles size={18} /><span><b>Let’s begin.</b> What is the legal name of your company?</span></div>
              <div className="form-grid compliance-form">
                <Field label="Full name" name="name" value={user.name} />
                <Field label="Legal company name" name="company" value={user.company} />
                <Field label="Registration number" name="registration" value={user.registration} />
                <Field label="Registered address" name="address" value={user.address} />
                <Field label="Phone" name="phone" value={user.phone} />
                <label className="field"><span>Buyer country</span><NativeSelect name="country" defaultValue={user.country}>{countries.map((country) => <option key={country}>{country}</option>)}</NativeSelect></label>
              </div>
              <div className="stage-actions"><span>Changes restart verification to protect your account.</span><Button disabled={busy} type="submit">Save & continue <ArrowRight size={16} /></Button></div>
            </form>
          )}

          {step === 2 && (
            <DocumentStage
              docs={docs}
              required={required}
              validKinds={validKinds}
              busy={busy}
              onUpload={onUpload}
              onContinue={() => setStep(3)}
            />
          )}

          {step === 3 && (
            <div className="stage-copy">
              <p className="eyebrow">FINAL CHECK</p>
              <h2>Review before submitting.</h2>
              <p>Your application goes to a human reviewer. Submission does not guarantee approval.</p>
              <div className="review-grid">
                <ReviewCard title="Account" value={user.email} done />
                <ReviewCard title="Company" value={user.company || 'Incomplete'} done={profileComplete} />
                <ReviewCard title="Registration" value={user.registration || 'Incomplete'} done={profileComplete} />
                <ReviewCard title="Documents" value={`${validKinds.size} of ${required.length} ready`} done={documentsComplete} />
              </div>
              <div className="trust-note"><ShieldCheck /><div><b>Trade access stays locked during review.</b><p>Only an authorized BlueHarbor staff member can approve your account.</p></div></div>
              <Button disabled={busy || !profileComplete || !documentsComplete} onClick={async () => { if (await onSubmit()) setStep(4); }}>Submit for human review <ArrowRight size={16} /></Button>
            </div>
          )}

          {step === 4 && (
            <div className="stage-copy status-stage">
              <span className={`stage-icon ${user.verified === 'VERIFIED' ? 'verified' : ''}`}><ShieldCheck size={30} /></span>
              <p className="eyebrow">APPLICATION STATUS</p>
              <h2>{statusTitle(user.verified)}</h2>
              <p>{statusMessage(user.verified)}</p>
              <div className="status-timeline">
                <Timeline label="Account confirmed" done />
                <Timeline label="Company details completed" done={profileComplete} />
                <Timeline label="Documents completed" done={documentsComplete} />
                <Timeline label="Submitted to BlueHarbor" done={submitted || user.verified === 'VERIFIED'} />
                <Timeline label="Trading access approved" done={user.verified === 'VERIFIED'} />
              </div>
              {user.verified === 'DRAFT' && <Button onClick={() => setStep(maxUnlocked)}>Continue application <ArrowRight size={16} /></Button>}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function Field({ label, name, value }: { label: string; name: string; value: string }) {
  return <label className="field"><span>{label}</span><Input name={name} defaultValue={value} required maxLength={500} /></label>;
}

function DocumentStage({ docs, required, validKinds, busy, onUpload, onContinue }: {
  docs: Doc[]; required: string[]; validKinds: Set<string>; busy: boolean;
  onUpload: Props['onUpload']; onContinue: () => void;
}) {
  const [kind, setKind] = useState(required.find((item) => !validKinds.has(item)) || required[0] || '');
  const [expiry, setExpiry] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const complete = required.length > 0 && required.every((item) => validKinds.has(item));
  async function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    const ok = await onUpload(file, kind, expiry);
    if (ok) { setFile(null); setExpiry(''); }
  }
  return (
    <div className="stage-copy">
      <p className="eyebrow">DOCUMENT CHECKLIST</p>
      <h2>Show us the business behind the account.</h2>
      <p>For a buyer registered in this country, the following current documents are required.</p>
      <div className="document-checklist">
        {required.map((item) => {
          const doc = docs.find((entry) => entry.kind === item && entry.expiry >= new Date().toISOString().slice(0, 10));
          return <div key={item} className={doc ? 'ready' : ''}><span>{doc ? <Check size={16} /> : <FileText size={16} />}</span><div><b>{item}</b><small>{doc ? `${doc.name} · valid to ${doc.expiry}` : 'Current document required'}</small></div>{doc && <a href={`/api/document/${doc.id}`}>View</a>}</div>;
        })}
      </div>
      <form className="upload-studio" onSubmit={submit}>
        <div><label className="field" htmlFor="compliance-kind"><span>Document type</span><NativeSelect id="compliance-kind" value={kind} onChange={(e) => setKind(e.target.value)}>{required.map((item) => <option key={item}>{item}</option>)}</NativeSelect></label><label className="field" htmlFor="compliance-expiry"><span>Expiry date</span><Input id="compliance-expiry" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} required /></label></div>
        <label className="drop-zone" htmlFor="compliance-document"><UploadCloud /><b>{file ? file.name : 'Drop or choose a document'}</b><small>PDF, PNG or JPG · maximum 5 MB · private storage</small><input id="compliance-document" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} required /></label>
        <Button type="submit" disabled={busy || !file}>Upload securely</Button>
      </form>
      <div className="stage-actions"><span>{complete ? 'Every required document is ready.' : 'Complete the checklist to unlock review.'}</span><Button disabled={!complete} onClick={onContinue}>Review application <ArrowRight size={16} /></Button></div>
    </div>
  );
}

function ReviewCard({ title, value, done }: { title: string; value: string; done: boolean }) {
  return <div className={done ? 'review-card ready' : 'review-card'}><span>{done ? <Check size={15} /> : '!'}</span><small>{title}</small><b>{value}</b></div>;
}

function Timeline({ label, done }: { label: string; done: boolean }) {
  return <div className={done ? 'done' : ''}><span>{done && <Check size={13} />}</span><b>{label}</b></div>;
}

function statusTitle(status: string) {
  if (status === 'VERIFIED') return 'You’re cleared to trade.';
  if (status === 'UNDER_REVIEW') return 'Your review is underway.';
  if (status === 'ADDITIONAL_INFORMATION_REQUIRED') return 'We need one more update.';
  return 'Your application is in progress.';
}

function statusMessage(status: string) {
  if (status === 'VERIFIED') return 'Your buyer identity is approved. You can now reserve available seafood and create orders.';
  if (status === 'UNDER_REVIEW') return 'BlueHarbor staff are reviewing your company and documents. Trading stays locked until approval.';
  if (status === 'ADDITIONAL_INFORMATION_REQUIRED') return 'Open the Documents stage, review the staff note, and replace the requested information.';
  return 'Continue the next incomplete stage. Your progress is saved in your secure workspace.';
}
