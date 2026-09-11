"""Phase 5 Gemini assistance.

Gemini is intentionally advisory only. This module exposes read/analyse/draft
operations and never calls operational mutation functions. All operational
approvals remain in the existing human-controlled admin workflows.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import urllib.error
import urllib.request
from typing import Any

MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash').strip() or 'gemini-3.8-flash'
API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
API_BASE = os.environ.get('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com/v1beta').rstrip('/')
MAX_INLINE_BYTES = int(os.environ.get('GEMINI_MAX_INLINE_BYTES', str(18 * 1024 * 1024)))
ALLOW_BUYER_DOCUMENTS = os.environ.get('GEMINI_ALLOW_BUYER_DOCUMENTS', 'false').lower() in ('1', 'true', 'yes')

SENSITIVE_DOCUMENT_TERMS = (
    'representative id', 'passport', 'aadhaar', 'aadhar', 'national id',
    'identity card', 'driver licence', 'driver license', 'personal id',
)
SENSITIVE_KEYS = {
    'email', 'phone', 'address', 'password', 'auth_uid', 'token', 'secret',
    'session', 'access_token', 'refresh_token', 'representative_id',
}

EMAIL_RE = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I)
PHONE_RE = re.compile(r'(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)')

SYSTEM = """You are the BlueHarbor document and operations assistant.
You analyse only the supplied BlueHarbor records and documents. Never claim to
have verified a buyer, released quality, cleared customs, changed inventory, or
approved a financial action. Those decisions are human-controlled. Treat all
model findings as proposed review assistance. Do not invent missing values.
When the prompt supplies source labels such as [S1], cite only those labels.
Return concise, professional JSON only when JSON is requested."""


def configured() -> bool:
    return bool(API_KEY)


def _require_role(S, staff, *roles):
    if staff['role'] != 'ADMIN' and staff['role'] not in roles:
        raise S.APIError('Your staff role does not allow this Gemini assistance task.', 403)


def _redact_text(value: str) -> str:
    value = EMAIL_RE.sub('[REDACTED_EMAIL]', value)
    value = PHONE_RE.sub('[REDACTED_PHONE]', value)
    return value


def _redact_obj(value: Any, key: str = '') -> Any:
    if key.lower() in SENSITIVE_KEYS:
        return '[REDACTED]'
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {k: _redact_obj(v, k) for k, v in value.items() if k.lower() not in {'content', 'password'}}
    if isinstance(value, (list, tuple)):
        return [_redact_obj(v) for v in value]
    return value


def _row(row) -> dict:
    return _redact_obj(dict(row)) if row else {}


def _json(value: Any) -> str:
    return json.dumps(_redact_obj(value), ensure_ascii=False, default=str, separators=(',', ':'))


def _source(kind: str, entity_id: Any, label: str, citation: str, href: str) -> dict:
    return {'citation': citation, 'kind': kind, 'id': str(entity_id), 'label': label, 'href': href}


def _filter_citations(result: dict, sources: list[dict]) -> dict:
    allowed = {s['citation'] for s in sources}
    raw = result.get('citations', [])
    if not isinstance(raw, list):
        raw = []
    result['citations'] = [str(x) for x in raw if str(x) in allowed]
    return result


def _gemini(parts: list[dict], *, json_mode: bool = True) -> dict | str:
    if not configured():
        raise RuntimeError('Gemini is not configured. Add GEMINI_API_KEY to the backend environment.')
    payload = {
        'systemInstruction': {'parts': [{'text': SYSTEM}]},
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': 0.15,
            'thinkingConfig': {'thinkingLevel': 'medium'},
            **({'responseMimeType': 'application/json'} if json_mode else {}),
        },
    }
    req = urllib.request.Request(
        f'{API_BASE}/models/{MODEL}:generateContent',
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
        headers={'Content-Type': 'application/json', 'x-goog-api-key': API_KEY},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode('utf-8'))
            message = body.get('error', {}).get('message') or f'Gemini API returned HTTP {exc.code}.'
        except Exception:
            message = f'Gemini API returned HTTP {exc.code}.'
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError('Gemini service could not be reached from the backend.') from exc
    candidates = raw.get('candidates') or []
    if not candidates:
        raise RuntimeError('Gemini returned no candidate response.')
    output_parts = candidates[0].get('content', {}).get('parts', [])
    text = ''.join(str(p.get('text', '')) for p in output_parts if isinstance(p, dict)).strip()
    if not text:
        raise RuntimeError('Gemini returned an empty response.')
    if not json_mode:
        return _redact_text(text)
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I | re.S).strip()
    try:
        return _redact_obj(json.loads(text))
    except json.JSONDecodeError as exc:
        raise RuntimeError('Gemini returned an invalid structured response.') from exc


def _audit(c, staff, S, task: str, entity: str, prompt: str, sources: list[dict], result=None, error=''):
    status = 'FAILED' if error else 'COMPLETED'
    input_json = {
        'staff_id': staff['id'], 'staff_role': staff['role'], 'prompt': _redact_text(prompt),
        'sources': sources, 'redaction': 'structured sensitive fields, email and phone redaction; sensitive identity documents blocked',
        'human_approval_required': True,
    }
    output_json = {'result': result or {}, 'citations': sources}
    c.execute(
        'INSERT INTO ai_jobs(kind,entity_id,revision,status,attempts,model,input_json,output_json,error,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        (task, str(entity), secrets.token_hex(8), status, 1, MODEL, _json(input_json), _json(output_json), _redact_text(error)[:1500], S.now(), S.now()),
    )


def jobs_snapshot(c, staff) -> list[dict]:
    rows = c.execute('SELECT * FROM ai_jobs ORDER BY id DESC LIMIT 100').fetchall()
    output = []
    for row in rows:
        item = dict(row)
        try:
            meta = json.loads(item.get('input_json') or '{}')
        except Exception:
            meta = {}
        if staff['role'] != 'ADMIN' and meta.get('staff_id') != staff['id']:
            continue
        item['input_json'] = meta
        try:
            item['output_json'] = json.loads(item.get('output_json') or '{}')
        except Exception:
            item['output_json'] = {}
        item['error'] = _redact_text(item.get('error') or '')
        output.append(item)
        if len(output) >= 25:
            break
    return output


def _catalog(c, staff) -> dict:
    result = {'documents': [], 'orders': [], 'buyers': [], 'shipments': []}
    if staff['role'] in ('ADMIN', 'OPERATIONS'):
        result['orders'] = [
            {'id': r['id'], 'label': f"{r['id']} · {r['product_name']} · {r['company']}"}
            for r in c.execute('SELECT o.id,o.product_name,u.company FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.created DESC LIMIT 250').fetchall()
        ]
        result['documents'] += [
            {'scope': 'trade', 'id': r['id'], 'order_id': r['order_id'], 'kind': r['kind'], 'name': r['name'], 'mime': r['mime'], 'created': r['created']}
            for r in c.execute('SELECT id,order_id,kind,name,mime,created FROM trade_documents ORDER BY created DESC LIMIT 300').fetchall()
        ]
        result['shipments'] = [
            {'id': r['id'], 'label': f"{r['id']} · {r['origin_port']} → {r['destination_port']} · {r['status']}"}
            for r in c.execute('SELECT id,origin_port,destination_port,status FROM transport_shipments ORDER BY updated DESC LIMIT 200').fetchall()
        ]
    if staff['role'] in ('ADMIN', 'VERIFIER'):
        result['buyers'] = [
            {'id': r['id'], 'label': f"{r['company'] or r['name']} · {r['country']} · {r['verified']}"}
            for r in c.execute('SELECT id,name,company,country,verified FROM users ORDER BY id DESC LIMIT 250').fetchall()
        ]
        result['documents'] += [
            {'scope': 'buyer', 'id': r['id'], 'buyer_id': r['user_id'], 'kind': r['kind'], 'name': r['name'], 'mime': r['mime'], 'created': r['created'],
             'ai_allowed': ALLOW_BUYER_DOCUMENTS and not any(term in (r['kind'] or '').lower() for term in SENSITIVE_DOCUMENT_TERMS)}
            for r in c.execute('SELECT id,user_id,kind,name,mime,created FROM documents ORDER BY created DESC LIMIT 300').fetchall()
        ]
    return result


def _document(c, staff, S, scope: str, did: str):
    if scope == 'trade':
        _require_role(S, staff, 'OPERATIONS')
        row = c.execute('SELECT * FROM trade_documents WHERE id=?', (did,)).fetchone()
        if not row:
            raise S.APIError('Trade document not found.', 404)
        meta = dict(row)
        source = _source('trade_document', did, f"{meta['kind']} · {meta['order_id']}", 'S1', f'/api/admin/trade-document/{did}')
        return meta, source
    if scope == 'buyer':
        _require_role(S, staff, 'VERIFIER')
        row = c.execute('SELECT * FROM documents WHERE id=?', (did,)).fetchone()
        if not row:
            raise S.APIError('Buyer document not found.', 404)
        meta = dict(row)
        if not ALLOW_BUYER_DOCUMENTS:
            raise S.APIError('Gemini processing of buyer-submitted documents is disabled by default. Set GEMINI_ALLOW_BUYER_DOCUMENTS=true only after approving your data-processing policy.', 409)
        if any(term in (meta.get('kind') or '').lower() for term in SENSITIVE_DOCUMENT_TERMS):
            raise S.APIError('This identity document is intentionally excluded from Gemini processing and must be reviewed manually.', 409)
        source = _source('buyer_document', did, f"{meta['kind']} · buyer {meta['user_id']}", 'S1', f'/api/admin/document/{did}')
        return meta, source
    raise S.APIError('Unknown document scope.')


def _inline_document(meta: dict) -> dict:
    content = meta.get('content')
    if not isinstance(content, (bytes, bytearray)):
        raise RuntimeError('Document bytes are unavailable.')
    if len(content) > 5 * 1024 * 1024:
        raise RuntimeError('Document exceeds the configured 5 MB application limit.')
    return {'inline_data': {'mime_type': meta['mime'], 'data': base64.b64encode(content).decode('ascii')}}


def _order_bundle(c, S, order_id: str, include_files=True):
    order = c.execute('SELECT o.*,u.company,u.name buyer_name FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=?', (order_id,)).fetchone()
    if not order:
        raise S.APIError('Order not found.', 404)
    sources = []
    context = {'order': _row(order)}
    sources.append(_source('order', order_id, f'Order {order_id}', 'S1', f'/api/admin/ai-source/order/{order_id}'))
    citation_index = 2
    mapping = c.execute('SELECT shipment_id FROM shipment_orders WHERE order_id=?', (order_id,)).fetchone()
    if mapping:
        from shipping_core import shipment_snapshot
        shipment = shipment_snapshot(c, mapping['shipment_id'])
        if shipment:
            context['shipment'] = _redact_obj(shipment)
            sources.append(_source('shipment', mapping['shipment_id'], f"Shipment {mapping['shipment_id']}", f'S{citation_index}', f"/api/admin/ai-source/shipment/{mapping['shipment_id']}"))
            citation_index += 1
    legacy = c.execute('SELECT * FROM shipments WHERE order_id=?', (order_id,)).fetchone()
    if legacy:
        context['legacy_shipment'] = _row(legacy)
    docs = c.execute('SELECT * FROM trade_documents WHERE order_id=? ORDER BY created DESC', (order_id,)).fetchall()
    latest = {}
    for doc in docs:
        d = dict(doc)
        latest.setdefault((d.get('kind') or '').lower(), d)
    files = []
    total = 0
    for d in list(latest.values())[:10]:
        source = _source('trade_document', d['id'], f"{d['kind']} · {d['name']}", f'S{citation_index}', f"/api/admin/trade-document/{d['id']}")
        sources.append(source)
        citation_index += 1
        context.setdefault('documents', []).append(_redact_obj({k: v for k, v in d.items() if k != 'content'}))
        if include_files:
            content = d.get('content')
            if isinstance(content, (bytes, bytearray)) and total + len(content) <= MAX_INLINE_BYTES:
                files.append((source, d, content))
                total += len(content)
    return context, sources, files


def _call_and_audit(c, staff, S, task: str, entity: str, prompt: str, parts: list[dict], sources: list[dict]):
    try:
        result = _gemini(parts, json_mode=True)
        if not isinstance(result, dict):
            result = {'text': str(result)}
        result = _filter_citations(result, sources)
        _audit(c, staff, S, task, entity, prompt, sources, result=result)
        return {'result': result, 'sources': sources, 'model': MODEL, 'human_approval_required': True}
    except Exception as exc:
        _audit(c, staff, S, task, entity, prompt, sources, error=str(exc))
        if isinstance(exc, S.APIError):
            raise
        raise S.APIError(str(exc), 502)


def _extract(c, staff, S, d):
    scope = str(d.get('scope', '')).strip()
    did = str(d.get('document_id', '')).strip()
    meta, source = _document(c, staff, S, scope, did)
    prompt = f"""Extract operational review fields from [S1]. Document type hint: {meta.get('kind','')}.
Return JSON with keys: document_type, fields, inconsistencies, review_notes, confidence, citations.
fields must be an object and should capture, when present: order_id, invoice_number, packing_list_number,
certificate_number, shipment_reference, container_number, vessel, exporter, buyer, product, quantity,
net_weight_kg, gross_weight_kg, issue_date, shipment_date, expiry_date, country_of_origin, identifiers.
Do not return personal identity numbers, email addresses, phone numbers, home addresses, bank data, or signatures.
inconsistencies must be an array of short observations. confidence must be LOW, MEDIUM, or HIGH.
Citations may contain only S1. Missing fields must be omitted rather than guessed."""
    parts = [{'text': prompt + '\n[S1] Exact source document follows.'}, _inline_document(meta)]
    return _call_and_audit(c, staff, S, 'DOCUMENT_EXTRACTION', did, prompt, parts, [source])


def _compare(c, staff, S, d):
    _require_role(S, staff, 'OPERATIONS')
    order_id = str(d.get('order_id', '')).strip()
    context, sources, files = _order_bundle(c, S, order_id, include_files=True)
    prompt = """Compare the supplied order record, shipment record, and attached trade documents.
Focus on invoices, packing lists, certificates and shipment records. Identify inconsistent weights,
dates, organization names, order/shipment/container identifiers, quantities, destinations, and document numbers.
Return JSON with keys: summary, inconsistencies, matched_fields, missing_evidence, operational_risk, citations.
inconsistencies must be an array of objects with field, values, severity (INFO/WARNING/CRITICAL), explanation,
and citations. operational_risk must be LOW, MEDIUM, or HIGH. Do not make an approval decision."""
    parts = [{'text': prompt + '\nStructured database context with source labels:\n' + _json({'context': context, 'sources': sources})}]
    for source, meta, content in files:
        parts.extend([
            {'text': f"[{source['citation']}] {source['label']}"},
            {'inline_data': {'mime_type': meta['mime'], 'data': base64.b64encode(content).decode('ascii')}}
        ])
    return _call_and_audit(c, staff, S, 'DOCUMENT_COMPARISON', order_id, prompt, parts, sources)


def _exceptions(c, staff, S, d):
    _require_role(S, staff, 'OPERATIONS')
    order_id = str(d.get('order_id', '')).strip()
    context, sources, _ = _order_bundle(c, S, order_id, include_files=False)
    prompt = """Summarize operational exceptions for this order and shipment using only supplied records.
Prioritize customs holds/queries, reefer or temperature exceptions, missing or unreleased documents,
cutoff/ETA risks, identifier mismatches, and unresolved operational exceptions. Return JSON with keys:
executive_summary, exceptions, recommended_human_checks, citations. Each exception must include severity,
issue, evidence, owner_or_team, and citations. Recommendations are advisory only."""
    parts = [{'text': prompt + '\nContext:\n' + _json({'context': context, 'sources': sources})}]
    return _call_and_audit(c, staff, S, 'OPERATIONAL_EXCEPTION_SUMMARY', order_id, prompt, parts, sources)


def _draft(c, staff, S, d):
    _require_role(S, staff, 'OPERATIONS')
    order_id = str(d.get('order_id', '')).strip()
    kind = str(d.get('kind', 'BUYER_MESSAGE')).strip().upper()
    if kind not in ('BUYER_MESSAGE', 'COVER_LETTER'):
        raise S.APIError('Choose buyer message or cover letter.')
    instructions = _redact_text(str(d.get('instructions', '')).strip())[:2500]
    context, sources, _ = _order_bundle(c, S, order_id, include_files=False)
    prompt = f"""Draft a {'buyer-facing operational message' if kind == 'BUYER_MESSAGE' else 'professional document cover letter'}
for order {order_id}. Use only the supplied context. Do not state that customs, quality, buyer verification,
inventory, or finance is approved unless the database explicitly says so; even then describe it as a recorded
status, not an AI decision. Additional staff instruction: {instructions or 'None'}.
Return JSON with keys: subject, body, caution_notes, citations. The draft must require human review before sending."""
    parts = [{'text': prompt + '\nContext:\n' + _json({'context': context, 'sources': sources})}]
    return _call_and_audit(c, staff, S, 'DRAFT_' + kind, order_id, prompt, parts, sources)


def _search_context(c, staff, S):
    sources, records = [], []
    idx = 1
    if staff['role'] in ('ADMIN', 'OPERATIONS'):
        for r in c.execute('SELECT o.id,o.product_name,o.kg,o.total,o.status,o.destination,o.created,u.company FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.created DESC LIMIT 80').fetchall():
            citation = f'S{idx}'; idx += 1
            records.append({'citation': citation, 'type': 'order', 'record': _row(r)})
            sources.append(_source('order', r['id'], f"Order {r['id']} · {r['product_name']}", citation, f"/api/admin/ai-source/order/{r['id']}"))
        for r in c.execute('SELECT id,booking_reference,carrier,vessel,voyage,status,origin_port,destination_port,planned_departure,actual_departure,planned_arrival,actual_arrival,updated FROM transport_shipments ORDER BY updated DESC LIMIT 60').fetchall():
            citation = f'S{idx}'; idx += 1
            records.append({'citation': citation, 'type': 'shipment', 'record': _row(r)})
            sources.append(_source('shipment', r['id'], f"Shipment {r['id']} · {r['status']}", citation, f"/api/admin/ai-source/shipment/{r['id']}"))
        for r in c.execute('SELECT id,order_id,kind,name,published,version,created,status,issuer,document_number,issue_date,expiry_date FROM trade_documents ORDER BY created DESC LIMIT 100').fetchall():
            citation = f'S{idx}'; idx += 1
            records.append({'citation': citation, 'type': 'trade_document', 'record': _row(r)})
            sources.append(_source('trade_document', r['id'], f"{r['kind']} · {r['order_id']}", citation, f"/api/admin/trade-document/{r['id']}"))
        for r in c.execute("SELECT id,shipment_id,kind,severity,title,evidence,required_action,owner,due_at,status,created,updated FROM operational_exceptions ORDER BY updated DESC LIMIT 80").fetchall():
            citation = f'S{idx}'; idx += 1
            records.append({'citation': citation, 'type': 'exception', 'record': _row(r)})
            sources.append(_source('exception', r['id'], f"Exception {r['id']} · {r['title']}", citation, f"/api/admin/ai-source/exception/{r['id']}"))
    if staff['role'] in ('ADMIN', 'VERIFIER'):
        for r in c.execute('SELECT id,name,company,country,registration,verified,created FROM users ORDER BY id DESC LIMIT 80').fetchall():
            citation = f'S{idx}'; idx += 1
            records.append({'citation': citation, 'type': 'buyer', 'record': _row(r)})
            sources.append(_source('buyer', r['id'], f"Buyer {r['company'] or r['name']}", citation, f"/api/admin/ai-source/buyer/{r['id']}"))
        for r in c.execute('SELECT id,user_id,kind,name,expiry,created FROM documents ORDER BY created DESC LIMIT 100').fetchall():
            citation = f'S{idx}'; idx += 1
            records.append({'citation': citation, 'type': 'buyer_document', 'record': _row(r)})
            sources.append(_source('buyer_document', r['id'], f"{r['kind']} · buyer {r['user_id']}", citation, f"/api/admin/document/{r['id']}"))
    return records, sources


def _search(c, staff, S, d):
    query = _redact_text(str(d.get('query', '')).strip())
    if not query or len(query) > 1000:
        raise S.APIError('Enter a natural-language search query up to 1000 characters.')
    records, sources = _search_context(c, staff, S)
    prompt = f"""Answer this natural-language search over the supplied BlueHarbor records: {query}
Return JSON with keys: answer, matches, citations. matches must be an array with citation, record_type,
identifier, and reason. Use only supplied source labels. If nothing matches, say so and return empty citations."""
    parts = [{'text': prompt + '\nRole-scoped searchable records:\n' + _json(records)}]
    result = _call_and_audit(c, staff, S, 'NATURAL_LANGUAGE_SEARCH', 'search', prompt, parts, sources)
    # Return only source links the model actually cited, avoiding an enormous link list.
    used = set(result['result'].get('citations', []))
    for match in result['result'].get('matches', []) if isinstance(result['result'].get('matches'), list) else []:
        if isinstance(match, dict) and match.get('citation'):
            used.add(str(match['citation']))
    result['sources'] = [s for s in sources if s['citation'] in used]
    return result


def _source_record(h, c, staff, S, endpoint: str):
    parts = endpoint.split('/', 2)
    if len(parts) != 3:
        raise S.APIError('Invalid source link.', 404)
    _, kind, entity_id = parts
    if kind == 'order':
        _require_role(S, staff, 'OPERATIONS')
        row = c.execute('SELECT o.*,u.company,u.name buyer_name FROM orders o JOIN users u ON u.id=o.user_id WHERE o.id=?', (entity_id,)).fetchone()
    elif kind == 'shipment':
        _require_role(S, staff, 'OPERATIONS')
        from shipping_core import shipment_snapshot
        value = shipment_snapshot(c, entity_id)
        if not value:
            raise S.APIError('Source record not found.', 404)
        h.send(_redact_obj(value)); return None
    elif kind == 'exception':
        _require_role(S, staff, 'OPERATIONS')
        row = c.execute('SELECT * FROM operational_exceptions WHERE id=?', (int(entity_id),)).fetchone()
    elif kind == 'buyer':
        _require_role(S, staff, 'VERIFIER')
        row = c.execute('SELECT id,name,company,country,registration,verified,created FROM users WHERE id=?', (int(entity_id),)).fetchone()
    else:
        raise S.APIError('Unknown source type.', 404)
    if not row:
        raise S.APIError('Source record not found.', 404)
    h.send(_row(row)); return None


def route(h, c, staff, endpoint: str, d: dict, write: bool, S):
    if endpoint == 'ai-status' and not write:
        return {
            'configured': configured(), 'model': MODEL,
            'buyer_document_ai_enabled': ALLOW_BUYER_DOCUMENTS,
            'advisory_only': True,
            'controls': ['Buyer verification', 'Quality release', 'Customs clearance', 'Inventory changes', 'Financial approvals'],
        }
    if endpoint == 'ai-catalog' and not write:
        return _catalog(c, staff)
    if endpoint.startswith('ai-source/') and not write:
        return _source_record(h, c, staff, S, endpoint)
    if not write:
        raise S.APIError('Not found.', 404)
    if endpoint == 'ai-extract': return _extract(c, staff, S, d)
    if endpoint == 'ai-compare': return _compare(c, staff, S, d)
    if endpoint == 'ai-exceptions': return _exceptions(c, staff, S, d)
    if endpoint == 'ai-draft': return _draft(c, staff, S, d)
    if endpoint == 'ai-search': return _search(c, staff, S, d)
    raise S.APIError('Unknown Gemini assistance task.', 404)
