import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, X, Send, Sparkles, Bot, User, UserRound, Headset } from 'lucide-react';
import { useModal } from '../../context/ModalContext';
import { isExternal, useCms } from '../../context/CmsContext';
import { api, ApiError } from '../../lib/api';

interface Msg {
  id: number;
  sender: 'visitor' | 'bot' | 'agent' | 'system';
  body: string;
  agent?: string;
  action?: string;
  links?: { label: string; url: string }[];
  ai?: boolean;
}
type ConvStatus = 'bot' | 'waiting' | 'active' | 'closed';

const KEY = 'aub_chat_token';
const getTok = () => { try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; } };
const setTok = (t: string) => { try { t ? sessionStorage.setItem(KEY, t) : sessionStorage.removeItem(KEY); } catch { /* private mode: chat just won't resume */ } };

/**
 * Website chat. Talks to the Django chat API (conversations are saved and visible in the dashboard).
 * Answers come from the knowledge base / site content, or from an AI provider ONLY when one is connected and enabled in the dashboard;
 * the header and each AI message say so honestly. A visitor can ask for a human at any time (when enabled).
 */
export const AIChatWidget: React.FC = () => {
  const { data } = useCms();
  const cfg = data?.chatbot;
  const { openQuoteModal } = useModal();
  const [isOpen, setIsOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [status, setStatus] = useState<ConvStatus>('bot');
  const [token, setToken] = useState(getTok());
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showContact, setShowContact] = useState(false);
  const [contact, setContact] = useState({ name: '', email: '', phone: '' });
  const [contactDone, setContactDone] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const lastId = useRef(0);

  const add = useCallback((incoming: Msg[]) => {
    if (!incoming.length) return;
    setMsgs((prev) => {
      const seen = new Set(prev.map((m) => m.id));
      const fresh = incoming.filter((m) => !seen.has(m.id));
      return fresh.length ? [...prev, ...fresh] : prev;
    });
    lastId.current = Math.max(lastId.current, ...incoming.map((m) => m.id));
  }, []);

  const start = useCallback(async () => {
    setError('');
    try {
      const r = await api<{ token: string; status: ConvStatus; messages: Msg[] }>('/chat/start/', { method: 'POST', json: { page: window.location.pathname } });
      setTok(r.token); setToken(r.token); setStatus(r.status); lastId.current = 0; setMsgs([]); add(r.messages);
    } catch (e) {
      setError((e as ApiError).message || 'Chat is unavailable right now.');
    }
  }, [add]);

  // Open → resume the saved conversation or start one.
  useEffect(() => {
    if (!isOpen || msgs.length || !cfg?.enabled) return;
    const t = getTok();
    if (!t) { start(); return; }
    api<{ status: ConvStatus; messages: Msg[] }>(`/chat/${t}/messages/?after=0`)
      .then((r) => { setStatus(r.status); if (r.status === 'closed' || !r.messages.length) start(); else add(r.messages); })
      .catch(() => start());
  }, [isOpen, cfg?.enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll for staff replies while a human is involved (or has been requested).
  useEffect(() => {
    if (!isOpen || !token || (status !== 'waiting' && status !== 'active')) return;
    const id = window.setInterval(() => {
      api<{ status: ConvStatus; messages: Msg[] }>(`/chat/${token}/messages/?after=${lastId.current}`)
        .then((r) => { setStatus(r.status); add(r.messages); })
        .catch(() => {});
    }, 5000);
    return () => window.clearInterval(id);
  }, [isOpen, token, status, add]);

  useEffect(() => { if (isOpen) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [msgs, isOpen, showContact]);

  const send = async (text?: string) => {
    const body = (text ?? input).trim();
    if (!body || busy || !token) return;
    setBusy(true); setError(''); setInput('');
    try {
      const r = await api<{ status: ConvStatus; visitorMessage: Msg; messages: Msg[] }>(`/chat/${token}/messages/`, { method: 'POST', json: { message: body } });
      setStatus(r.status); add([r.visitorMessage, ...r.messages]);
    } catch (e) {
      const ae = e as ApiError;
      if (ae.status === 409) { setTok(''); await start(); } else setError(ae.message || 'Message not sent. Please try again.');
      setInput(body);
    } finally { setBusy(false); }
  };

  const handoff = async () => {
    if (!token || busy) return;
    setBusy(true); setError('');
    try {
      const r = await api<{ status: ConvStatus; messages: Msg[] }>(`/chat/${token}/handoff/`, { method: 'POST', json: {} });
      setStatus(r.status); add(r.messages);
    } catch (e) { setError((e as ApiError).message || 'Could not reach a team member right now.'); } finally { setBusy(false); }
  };

  const sendContact = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      await api(`/chat/${token}/contact/`, { method: 'POST', json: contact });
      setContactDone(true); setShowContact(false);
      const r = await api<{ status: ConvStatus; messages: Msg[] }>(`/chat/${token}/messages/?after=${lastId.current}`);
      add(r.messages);
    } catch (err) {
      const ae = err as ApiError;
      const first = ae.details ? Object.values(ae.details)[0] : '';
      setError((Array.isArray(first) ? first[0] : first) || ae.message);
    } finally { setBusy(false); }
  };

  if (!cfg || !cfg.enabled) return null;

  const subtitle =
    status === 'active' ? 'You are chatting with our team'
    : status === 'waiting' ? 'Waiting for a team member to join'
    : cfg.aiEnabled ? 'AI-assisted · a person can step in on request'
    : 'Automated assistant · answers common questions';
  const quick = msgs.length <= 1 && status === 'bot' ? cfg.quickReplies : [];

  return (
    <div className="fixed right-4 sm:right-6 bottom-[max(1rem,env(safe-area-inset-bottom))] sm:bottom-6 z-40">
      <AnimatePresence>
        {isOpen && (
          <motion.div
            role="dialog" aria-label={`${cfg.botName} chat`}
            initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="w-[calc(100vw-2rem)] sm:w-[380px] h-[min(540px,calc(100dvh-7rem))] rounded-3xl bg-[#120D24] border border-aub-border/90 shadow-2xl flex flex-col overflow-hidden mb-4 mr-0"
          >
            <div className="p-4 bg-aub-card/90 border-b border-aub-border/80 flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-9 h-9 rounded-xl bg-aub-gradient flex items-center justify-center shrink-0">
                  {status === 'active' ? <Headset className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-white" />}
                </div>
                <div className="min-w-0">
                  <h4 className="text-sm font-bold text-white font-display truncate">{cfg.botName}</h4>
                  <p className="text-[11px] text-aub-accent-labels truncate">{subtitle}</p>
                </div>
              </div>
              <button onClick={() => setIsOpen(false)} className="w-9 h-9 rounded-full hover:bg-white/10 flex items-center justify-center text-aub-text-secondary hover:text-white transition-colors" aria-label="Close chat">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div data-lenis-prevent className="flex-1 min-h-0 p-4 overflow-y-auto overscroll-contain space-y-3" aria-live="polite">
              {msgs.length === 0 && !error && <p className="text-xs text-aub-text-secondary">Connecting…</p>}
              {msgs.map((m) => m.sender === 'system' ? (
                <p key={m.id} className="text-center text-[11px] text-aub-text-secondary px-3">{m.body}</p>
              ) : (
                <div key={m.id} className={`flex gap-2.5 ${m.sender === 'visitor' ? 'justify-end' : 'justify-start'}`}>
                  {m.sender !== 'visitor' && (
                    <div className="w-7 h-7 rounded-lg bg-aub-card border border-aub-border flex items-center justify-center shrink-0 mt-0.5">
                      {m.sender === 'agent' ? <UserRound className="w-3.5 h-3.5 text-aub-accent-labels" /> : <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />}
                    </div>
                  )}
                  <div className="max-w-[82%] space-y-2">
                    {m.sender === 'agent' && m.agent && <span className="block text-[10px] text-aub-accent-labels font-semibold">{m.agent}</span>}
                    <div className={`p-3 rounded-2xl text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words ${m.sender === 'visitor' ? 'bg-aub-gradient text-white rounded-tr-none' : 'bg-aub-card border border-aub-border text-aub-text-primary rounded-tl-none'}`}>
                      {m.body}
                    </div>
                    {m.ai && <span className="block text-[10px] text-aub-text-secondary">AI-generated reply — may contain mistakes</span>}
                    {m.action === 'quote' && (
                      <button onClick={() => { setIsOpen(false); openQuoteModal(); }} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-aub-gradient text-[11px] font-semibold text-white shadow-glow-magenta hover:scale-105 transition-transform">
                        <Sparkles className="w-3 h-3" /><span>Request Free Quote</span>
                      </button>
                    )}
                    {(m.links || []).map((l) => isExternal(l.url)
                      ? <a key={l.url} href={l.url} target="_blank" rel="noopener noreferrer" className="block text-[11px] font-semibold text-aub-accent-labels underline">{l.label}</a>
                      : <Link key={l.url} to={l.url} onClick={() => setIsOpen(false)} className="block text-[11px] font-semibold text-aub-accent-labels underline">{l.label}</Link>)}
                  </div>
                  {m.sender === 'visitor' && (
                    <div className="w-7 h-7 rounded-lg bg-aub-purple/30 border border-aub-purple/50 flex items-center justify-center shrink-0 mt-0.5"><User className="w-3.5 h-3.5 text-white" /></div>
                  )}
                </div>
              ))}

              {showContact && (
                <form onSubmit={sendContact} className="p-3 rounded-2xl bg-aub-card border border-aub-border space-y-2">
                  <p className="text-[11px] text-aub-text-secondary">Leave your details and we can follow up if we miss you here.</p>
                  <input required aria-label="Your name" placeholder="Name" autoComplete="name" value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} className="w-full bg-aub-bg/60 border border-aub-border px-3 py-2 rounded-lg text-base sm:text-xs text-white" />
                  <input required type="email" aria-label="Your email" placeholder="Email" autoComplete="email" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} className="w-full bg-aub-bg/60 border border-aub-border px-3 py-2 rounded-lg text-base sm:text-xs text-white" />
                  <input type="tel" aria-label="Phone (optional)" placeholder="Phone / WhatsApp (optional)" autoComplete="tel" value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} className="w-full bg-aub-bg/60 border border-aub-border px-3 py-2 rounded-lg text-base sm:text-xs text-white" />
                  <div className="flex gap-2">
                    <button type="submit" disabled={busy} className="flex-1 min-h-[38px] rounded-full bg-aub-gradient text-white text-xs font-bold disabled:opacity-60">Send details</button>
                    <button type="button" onClick={() => setShowContact(false)} className="px-4 min-h-[38px] rounded-full glass-panel text-xs text-white">Cancel</button>
                  </div>
                </form>
              )}
              {error && <p role="alert" className="text-[11px] text-red-300 text-center">{error}</p>}
              <div ref={endRef} />
            </div>

            {(quick.length > 0 || (cfg.humanHandoff && status === 'bot') || (cfg.askContact && !contactDone && !showContact)) && (
              <div className="px-3 py-2 bg-aub-card/40 border-t border-aub-border/50 flex gap-1.5 overflow-x-auto no-scrollbar">
                {quick.map((q) => (
                  <button key={q} onClick={() => send(q)} disabled={busy} className="px-2.5 py-1 rounded-full bg-aub-card border border-aub-border/80 text-[11px] text-aub-text-secondary hover:text-white hover:border-aub-magenta/50 shrink-0 transition-colors whitespace-nowrap">{q}</button>
                ))}
                {cfg.humanHandoff && status === 'bot' && (
                  <button onClick={handoff} disabled={busy} className="px-2.5 py-1 rounded-full bg-aub-purple/20 border border-aub-purple/50 text-[11px] text-white shrink-0 whitespace-nowrap">Talk to a person</button>
                )}
                {cfg.askContact && !contactDone && !showContact && (
                  <button onClick={() => setShowContact(true)} className="px-2.5 py-1 rounded-full bg-aub-card border border-aub-border/80 text-[11px] text-aub-text-secondary hover:text-white shrink-0 whitespace-nowrap">Leave my details</button>
                )}
              </div>
            )}

            <form onSubmit={(e) => { e.preventDefault(); send(); }} className="p-3 bg-aub-card/80 border-t border-aub-border flex items-center gap-2">
              <input type="text" maxLength={1000} aria-label="Your message" placeholder="Type your message…" value={input} onChange={(e) => setInput(e.target.value)}
                className="flex-1 min-w-0 bg-aub-bg/60 border border-aub-border px-3.5 py-2 min-h-[40px] rounded-xl text-base sm:text-sm text-white placeholder-white/30 focus:outline-none focus:border-aub-magenta" />
              <button type="submit" disabled={busy || !input.trim() || !token} className="w-10 h-10 rounded-xl bg-aub-gradient flex items-center justify-center text-white shadow-glow-magenta hover:scale-105 transition-transform disabled:opacity-50" aria-label="Send message">
                <Send className="w-4 h-4" />
              </button>
            </form>
            {cfg.privacyNotice && <p className="px-4 pb-3 pt-0 bg-aub-card/80 text-[10px] leading-snug text-aub-text-secondary">{cfg.privacyNotice}</p>}
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.95 }} onClick={() => setIsOpen(!isOpen)} aria-expanded={isOpen}
        className="w-14 h-14 rounded-full bg-aub-gradient flex items-center justify-center text-white shadow-glow-magenta hover:shadow-glow-purple border border-white/30 transition-shadow relative"
        aria-label={isOpen ? 'Close chat' : 'Open chat'}>
        {isOpen ? <X className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
      </motion.button>
    </div>
  );
};
