"""Opt-in SMTP delivery. No email is sent until an owner configures and enables it."""
import os
import smtplib
import ssl
from email.message import EmailMessage
import admin_core as A

def configured():return bool(os.environ.get('BLUEHARBOR_SMTP_HOST') and os.environ.get('BLUEHARBOR_SMTP_FROM'))
def queue_status(c,uid):
    u=c.execute('SELECT email FROM users WHERE id=?',(uid,)).fetchone()
    return 'QUEUED' if configured() and A.settings(c).get('email_enabled') and u and not u['email'].endswith('.local') else 'NOT_CONNECTED'
def process_one():
    if not configured():return
    with A.S.db() as c:
        if not A.settings(c).get('email_enabled'):return
        c.execute('BEGIN IMMEDIATE')
        row=c.execute("SELECT e.*,u.email FROM email_outbox e JOIN users u ON u.id=e.user_id WHERE e.status='QUEUED' ORDER BY e.id LIMIT 1").fetchone()
        if not row:return
        row=dict(row);c.execute("UPDATE email_outbox SET status='SENDING',attempts=attempts+1,updated=? WHERE id=?",(A.S.now(),row['id']))
    try:
        message=EmailMessage();message['From']=os.environ['BLUEHARBOR_SMTP_FROM'];message['To']=row['email'];message['Subject']=row['subject'];message.set_content(row['body'])
        mode=os.environ.get('BLUEHARBOR_SMTP_SECURITY','ssl');port=int(os.environ.get('BLUEHARBOR_SMTP_PORT','465' if mode=='ssl' else '587'))
        if mode not in ('ssl','starttls'):raise ValueError('Only encrypted SMTP is supported.')
        if mode=='ssl':client=smtplib.SMTP_SSL(os.environ['BLUEHARBOR_SMTP_HOST'],port,timeout=20,context=ssl.create_default_context())
        else:
            client=smtplib.SMTP(os.environ['BLUEHARBOR_SMTP_HOST'],port,timeout=20);client.starttls(context=ssl.create_default_context())
        with client:
            if os.environ.get('BLUEHARBOR_SMTP_USER'):client.login(os.environ['BLUEHARBOR_SMTP_USER'],os.environ.get('BLUEHARBOR_SMTP_PASSWORD',''))
            client.send_message(message)
        status,error='SENT',''
    except Exception as exc:status,error='FAILED',type(exc).__name__+': delivery failed; check SMTP settings and provider logs.'
    with A.S.db() as c:
        c.execute('UPDATE email_outbox SET status=?,error=?,updated=? WHERE id=?',(status,error,A.S.now(),row['id']));A.change(c)
