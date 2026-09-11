'use client';

import { useState } from 'react';
import { Fish, Languages, Send, Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

type Message = { role: 'guide' | 'buyer'; text: string };

export default function BlueHarborGuide({
  signedIn,
  verified,
  onNavigate,
}: {
  signedIn: boolean;
  verified?: string;
  onNavigate: (view: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'guide',
      text: 'Hi, I’m BlueHarbor Gemini. I can answer from your shipment records, summarize delays and document status, draft shipment or claim messages, and explain records in your preferred language.',
    },
  ]);

  const prompts = signedIn
    ? verified === 'VERIFIED'
      ? [
          'Summarize my shipment delays and document status',
          'Draft a follow-up message for my latest shipment',
          'Draft a claim description from my latest exception',
          'Explain my latest shipment in Tamil',
        ]
      : [
          'Do I have any shipment records yet?',
          'Explain my available order records',
          'Explain this in Tamil',
        ]
    : ['What can BlueHarbor Gemini help with?'];

  async function ask(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const nextHistory = [...messages, { role: 'buyer' as const, text: message }];
    setMessages(nextHistory);
    setInput('');
    if (!signedIn) {
      setMessages((items) => [
        ...items,
        {
          role: 'guide',
          text: 'Sign in first. Gemini is intentionally restricted to the signed-in buyer’s own BlueHarbor order and shipment records.',
        },
      ]);
      return;
    }
    setBusy(true);
    try {
      const response = await fetch('/api/guide', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-BlueHarbor': '1' },
        body: JSON.stringify({
          message,
          view: window.location.hash.slice(1),
          history: messages.slice(-8),
        }),
      });
      const result = (await response.json()) as {
        answer?: string;
        navigate?: string;
        error?: string;
        model?: string;
      };
      if (!response.ok) throw new Error(result.error || 'Gemini unavailable');
      setMessages((items) => [
        ...items,
        { role: 'guide', text: result.answer || 'I could not find enough shipment evidence to answer that.' },
      ]);
      if (result.navigate) onNavigate(result.navigate);
    } catch (error) {
      setMessages((items) => [
        ...items,
        {
          role: 'guide',
          text:
            error instanceof Error
              ? error.message
              : 'Gemini is temporarily unavailable. Your orders and shipment records remain accessible in the portal.',
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        className={`gemini-fish-launcher${open ? ' open' : ''}`}
        onClick={() => setOpen(!open)}
        aria-label={open ? 'Close BlueHarbor Gemini' : 'Open BlueHarbor Gemini'}
        title="BlueHarbor Gemini"
      >
        {open ? <X size={24} /> : <Fish size={30} />}
        {!open && <Sparkles className="gemini-spark" size={14} />}
      </button>
      {open && (
        <aside className="guide-panel gemini-panel" aria-label="BlueHarbor Gemini shipment assistant">
          <header>
            <span className="gemini-avatar"><Fish size={22} /></span>
            <div>
              <small>GEMINI POWERED</small>
              <b>BlueHarbor Gemini</b>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close assistant"><X /></button>
          </header>
          <div className="guide-context">
            <Sparkles size={15} />
            <span>Answers are scoped to your own BlueHarbor shipment records</span>
            <Languages size={15} />
          </div>
          <div className="guide-messages">
            {messages.map((message, index) => (
              <div key={index} className={message.role}>
                <span>{message.text}</span>
              </div>
            ))}
            {busy && (
              <div className="guide">
                <span className="thinking">Gemini is reviewing your shipment records<i /><i /><i /></span>
              </div>
            )}
          </div>
          <div className="guide-prompts">
            {prompts.map((prompt) => (
              <button key={prompt} onClick={() => void ask(prompt)}>{prompt}</button>
            ))}
          </div>
          <form onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
            <Input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about delays, documents, claims, or request a language…"
              maxLength={1200}
            />
            <Button type="submit" size="icon" disabled={busy || !input.trim()} aria-label="Send to Gemini">
              <Send size={16} />
            </Button>
          </form>
          <p>AI assistance only. Shipment operations, customs, quality, inventory, verification and financial approvals remain human-controlled.</p>
        </aside>
      )}
    </>
  );
}
