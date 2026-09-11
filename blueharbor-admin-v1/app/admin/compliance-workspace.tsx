'use client';

/* Buyer documents use authenticated same-origin URLs. */
/* oxlint-disable next/no-img-element */
import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  CheckCircle2,
  Clock3,
  FileText,
  MessageSquare,
  ShieldAlert,
  ShieldCheck,
  UserRoundCheck,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { NativeSelect } from '@/components/ui/native-select';

// Records are validated by the shared administrative API.
// oxlint-disable-next-line typescript/no-explicit-any
type Row = Record<string, any>;
type Action = (path: string, data: unknown) => Promise<boolean>;

const statusLabels: Record<string, string> = {
  DRAFT: 'Setup in progress',
  UNDER_REVIEW: 'Ready for review',
  VERIFIED: 'Approved to trade',
  ADDITIONAL_INFORMATION_REQUIRED: 'Needs more information',
  REJECTED: 'Not approved',
  SUSPENDED: 'Trading suspended',
  PENDING: 'Awaiting review',
  APPROVED: 'Approved',
};

function friendly(value: string) {
  return statusLabels[value] || value.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase());
}

export default function ComplianceWorkspace({
  buyers,
  team,
  detail,
  busy,
  openBuyer,
  closeBuyer,
  act,
}: {
  buyers: Row[];
  team: Row[];
  detail: Row | null;
  busy: boolean;
  openBuyer: (id: number) => Promise<void>;
  closeBuyer: () => void;
  act: Action;
}) {
  const [filter, setFilter] = useState('ACTION');
  const shown = useMemo(
    () => buyers.filter((buyer) => {
      if (filter === 'ALL') return true;
      if (filter === 'ACTION') return ['UNDER_REVIEW', 'ADDITIONAL_INFORMATION_REQUIRED'].includes(buyer.verified);
      return buyer.verified === filter;
    }),
    [buyers, filter],
  );

  if (detail) {
    const current = shown.findIndex((buyer) => buyer.id === detail.buyer.id);
    return (
      <CaseWorkspace
        detail={detail}
        team={team}
        busy={busy}
        back={closeBuyer}
        previous={current > 0 ? () => void openBuyer(shown[current - 1].id) : undefined}
        next={current >= 0 && current < shown.length - 1 ? () => void openBuyer(shown[current + 1].id) : undefined}
        act={act}
      />
    );
  }

  const ready = buyers.filter((buyer) => buyer.verified === 'UNDER_REVIEW').length;
  const corrections = buyers.filter((buyer) => buyer.verified === 'ADDITIONAL_INFORMATION_REQUIRED').length;
  const approved = buyers.filter((buyer) => buyer.verified === 'VERIFIED').length;
  return (
    <div className="compliance-admin">
      <section className="admin-hero compliance-hero">
        <div>
          <p className="admin-eyebrow">HUMAN-LED COMPLIANCE</p>
          <h1>Buyer review, without the guesswork.</h1>
          <p>Review company details and each required document before granting access to trade.</p>
        </div>
        <div className="compliance-hero-metrics">
          <span><b>{ready}</b>Ready now</span>
          <span><b>{corrections}</b>Needs information</span>
          <span><b>{approved}</b>Approved</span>
        </div>
      </section>
      <div className="workspace-toolbar">
        <div><b>Review queue</b><span>{shown.length} buyers in this view</span></div>
        <NativeSelect aria-label="Filter buyer review queue" value={filter} onChange={(event) => setFilter(event.target.value)}>
          <option value="ACTION">Needs staff action</option>
          <option value="UNDER_REVIEW">Ready for review</option>
          <option value="ADDITIONAL_INFORMATION_REQUIRED">Needs information</option>
          <option value="DRAFT">Setup in progress</option>
          <option value="VERIFIED">Approved</option>
          <option value="REJECTED">Not approved</option>
          <option value="SUSPENDED">Suspended</option>
          <option value="ALL">All buyers</option>
        </NativeSelect>
      </div>
      <div className="review-queue">
        {shown.map((buyer) => {
          const reviewer = team.find((person) => person.id === buyer.assignee);
          return (
            <button key={buyer.id} onClick={() => void openBuyer(buyer.id)}>
              <span className={`queue-icon state-${buyer.verified.toLowerCase()}`}>
                {buyer.verified === 'VERIFIED' ? <ShieldCheck /> : buyer.verified === 'UNDER_REVIEW' ? <Clock3 /> : <Building2 />}
              </span>
              <div>
                <small>{buyer.country} · {buyer.submitted ? `Submitted ${new Date(buyer.submitted).toLocaleDateString()}` : 'Not submitted'}</small>
                <h2>{buyer.company || buyer.name}</h2>
                <p>{buyer.email}</p>
              </div>
              <div className="queue-owner">
                <span className={`human-status status-${buyer.verified.toLowerCase()}`}>{friendly(buyer.verified)}</span>
                <small>{reviewer ? `Assigned to ${reviewer.name}` : 'Unassigned'}</small>
              </div>
              <ArrowRight />
            </button>
          );
        })}
        {!shown.length && <div className="queue-empty"><CheckCircle2 /><h2>This queue is clear.</h2><p>New buyer submissions will appear here automatically.</p></div>}
      </div>
    </div>
  );
}

function CaseWorkspace({
  detail: d,
  team,
  busy,
  back,
  previous,
  next,
  act,
}: {
  detail: Row;
  team: Row[];
  busy: boolean;
  back: () => void;
  previous?: () => void;
  next?: () => void;
  act: Action;
}) {
  const [docId, setDocId] = useState(d.documents[0]?.id || '');
  const [documentNote, setDocumentNote] = useState('');
  const [decision, setDecision] = useState('ADDITIONAL_INFORMATION_REQUIRED');
  const [decisionNote, setDecisionNote] = useState('');
  const [message, setMessage] = useState('');
  const doc = d.documents.find((item: Row) => item.id === docId) || d.documents[0];
  const today = new Date().toISOString().slice(0, 10);
  const checklist = d.required.map((kind: string) => {
    const document = d.documents.find((item: Row) => item.kind === kind && item.expiry >= today);
    return { kind, document, approved: document?.review_status === 'APPROVED' };
  });
  const approved = checklist.filter((item: Row) => item.approved).length;
  const ready = approved === checklist.length && checklist.length > 0 && d.buyer.verified === 'UNDER_REVIEW';
  const companyRows = [
    ['Legal company', d.buyer.company],
    ['Registration', d.buyer.registration],
    ['Registered address', d.buyer.address],
    ['Representative phone', d.buyer.phone],
  ];

  return (
    <div className="case-page">
      <header className="case-page-header">
        <Button variant="ghost" onClick={back}><ArrowLeft /> Back to queue</Button>
        <div>
          <Button variant="outline" size="icon" disabled={!previous} onClick={previous} aria-label="Previous buyer"><ArrowLeft /></Button>
          <Button variant="outline" size="icon" disabled={!next} onClick={next} aria-label="Next buyer"><ArrowRight /></Button>
        </div>
      </header>
      <section className="case-titlebar">
        <div className="case-company-mark">{(d.buyer.company || d.buyer.name).slice(0, 2).toUpperCase()}</div>
        <div><p className="admin-eyebrow">CASE #{d.buyer.id} · REVISION {d.case.revision}</p><h1>{d.buyer.company || d.buyer.name}</h1><p>{d.buyer.email} · {d.buyer.country}</p></div>
        <span className={`human-status status-${d.buyer.verified.toLowerCase()}`}>{friendly(d.buyer.verified)}</span>
      </section>
      <div className="case-progress">
        <div><span style={{ width: `${Math.round((approved / Math.max(checklist.length, 1)) * 100)}%` }} /></div>
        <b>{approved} of {checklist.length} required documents approved</b>
        <small>{ready ? 'All evidence is ready for a final human decision.' : 'Final approval stays locked until the checklist is complete.'}</small>
      </div>
      <div className="case-page-grid">
        <aside className="case-column company-evidence">
          <h2>Company identity</h2>
          {companyRows.map(([label, value]) => <div key={label}><small>{label}</small><b>{value || 'Not provided'}</b></div>)}
          <label>Assigned reviewer
            <NativeSelect value={d.case.assignee || ''} onChange={(event) => void act('assign-case', { user_id: d.buyer.id, assignee: Number(event.target.value) })}>
              <option value="" disabled>Choose reviewer</option>
              {team.filter((person) => person.active && ['ADMIN', 'VERIFIER'].includes(person.role)).map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
            </NativeSelect>
          </label>
        </aside>
        <main className="case-column document-evidence">
          <div className="column-heading"><div><h2>Required evidence</h2><p>Select a document to review it securely.</p></div><span>{approved}/{checklist.length}</span></div>
          <div className="document-tabs">
            {checklist.map((item: Row) => (
              <button key={item.kind} className={doc?.id === item.document?.id ? 'selected' : ''} disabled={!item.document} onClick={() => { setDocId(item.document.id); setDocumentNote(''); }}>
                <span>{item.approved ? <Check /> : item.document ? <FileText /> : <ShieldAlert />}</span>
                <div><b>{item.kind}</b><small>{item.document ? `${friendly(item.document.review_status)} · expires ${item.document.expiry}` : 'Current document missing'}</small></div>
              </button>
            ))}
          </div>
          <div className="secure-preview">
            {doc ? <>
              {doc.mime === 'application/pdf' ? <iframe title={`${doc.kind} preview`} src={`/api/admin/document/${doc.id}`} /> : doc.mime.startsWith('image/') ? <img alt={doc.kind} src={`/api/admin/document/${doc.id}`} /> : <div className="preview-unavailable"><FileText /><p>Open this file in a secure viewer.</p></div>}
              <a href={`/api/admin/document/${doc.id}`} target="_blank" rel="noreferrer">Open full document <ArrowRight /></a>
            </> : <div className="preview-unavailable"><ShieldAlert /><p>No current document is available for this requirement.</p></div>}
          </div>
          {doc && <section className="document-decision">
            <label>Document review note<textarea value={documentNote} onChange={(event) => setDocumentNote(event.target.value)} placeholder="Record the evidence supporting this document decision." maxLength={2000} /></label>
            <div>
              <Button variant="outline" disabled={busy || !documentNote.trim()} onClick={() => void act('document-review', { id: doc.id, status: 'REJECTED', reason: documentNote })}><XCircle /> Request replacement</Button>
              <Button disabled={busy || !documentNote.trim()} onClick={() => void act('document-review', { id: doc.id, status: 'APPROVED', reason: documentNote })}><Check /> Approve document</Button>
            </div>
          </section>}
        </main>
        <aside className="case-column final-decision">
          <h2>Final human decision</h2>
          <p className="decision-explainer">This decision controls whether the buyer can trade. Automated approval is disabled.</p>
          {!ready && <div className="decision-blocker"><ShieldAlert /><div><b>Approval is currently locked</b><p>{checklist.filter((item: Row) => !item.approved).map((item: Row) => item.kind).join(', ') || 'The buyer must submit the case for review.'}</p></div></div>}
          <label htmlFor="buyer-final-decision">Decision</label>
            <NativeSelect id="buyer-final-decision" value={decision} onChange={(event) => setDecision(event.target.value)}>
              <option value="ADDITIONAL_INFORMATION_REQUIRED">Needs more information</option>
              <option value="VERIFIED" disabled={!ready}>Approve buyer to trade</option>
              <option value="REJECTED">Do not approve</option>
              <option value="SUSPENDED">Suspend trading access</option>
              <option value="UNDER_REVIEW">Keep under review</option>
            </NativeSelect>
          <label>Buyer-visible decision message<textarea value={decisionNote} onChange={(event) => setDecisionNote(event.target.value)} placeholder="Explain the decision and the buyer's next step." maxLength={2000} /></label>
          <Button className="decision-submit" disabled={busy || !decisionNote.trim() || (decision === 'VERIFIED' && !ready)} onClick={() => void act('verification', { user_id: d.buyer.id, status: decision, reason: decisionNote, revision: d.case.revision })}><UserRoundCheck /> Save buyer decision</Button>
          <section className="case-message">
            <h3><MessageSquare /> Send a separate message</h3>
            <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Optional buyer-visible update" maxLength={2000} />
            <Button variant="outline" disabled={busy || !message.trim()} onClick={async () => { if (await act('notify', { user_id: d.buyer.id, message })) setMessage(''); }}>Send message</Button>
          </section>
        </aside>
      </div>
    </div>
  );
}
