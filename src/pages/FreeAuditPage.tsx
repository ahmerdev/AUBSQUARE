import React, { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, CheckCircle2, Gauge, Lock, Search, Sparkles, Wrench, XCircle } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { GlassCard } from '../components/ui/GlassCard';
import { api, ApiError } from '../lib/api';
import { useSite, whatsappLink } from '../context/CmsContext';

interface AuditCheck { key: string; label: string; ok: boolean }
interface AuditFinding { title: string; detail: string; fix: string }
interface AuditResult {
  token: string;
  url: string;
  reachable: boolean;
  error: string;
  score: number | null;
  health: number | null;
  level: string | null;
  loadSeconds: number | null;
  checks: AuditCheck[];
  findings: AuditFinding[];
  leadSent: boolean;
  checkedAt: string;
}

const inputCls =
  'w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border border-aub-border text-white text-base sm:text-sm placeholder:text-aub-text-secondary/70 focus:outline-none focus:ring-2 focus:ring-aub-magenta';

const levelText: Record<string, { label: string; colour: string }> = {
  high: { label: 'Needs a lot of improvement', colour: '#F43F5E' },
  medium: { label: 'Some clear gaps to fix', colour: '#F59E0B' },
  low: { label: 'In good shape', colour: '#22C55E' },
};

const ScoreRing: React.FC<{ score: number; colour: string }> = ({ score, colour }) => {
  const r = 52;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative w-36 h-36 shrink-0" role="img" aria-label={`Website health score ${score} out of 100`}>
      <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="9" />
        <motion.circle
          cx="60" cy="60" r={r} fill="none" stroke={colour} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - score / 100) }}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-extrabold font-display text-white">{score}</span>
        <span className="text-[11px] uppercase tracking-wider text-aub-text-secondary">out of 100</span>
      </div>
    </div>
  );
};

export const FreeAuditPage: React.FC = () => {
  const site = useSite();
  const wa = whatsappLink(site);
  const [url, setUrl] = useState('');
  const [running, setRunning] = useState(false);
  const [urlError, setUrlError] = useState('');
  const [result, setResult] = useState<AuditResult | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const [form, setForm] = useState({ name: '', email: '', phone: '', message: '', consent: false, website: '' });
  const [sending, setSending] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [sentRef, setSentRef] = useState('');

  const runAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (running) return;
    setUrlError('');
    setResult(null);
    setSentRef('');
    if (!url.trim()) {
      setUrlError('Please enter your website address, e.g. yourbusiness.com');
      return;
    }
    setRunning(true);
    try {
      const data = await api<AuditResult>('/audit/', { method: 'POST', json: { url: url.trim() } });
      setResult(data);
      if (data.leadSent) setSentRef('sent');
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    } catch (err) {
      if (err instanceof ApiError) {
        const d = err.details?.url;
        setUrlError((Array.isArray(d) ? d[0] : d) || err.message);
      } else {
        setUrlError('Something went wrong. Please try again.');
      }
    } finally {
      setRunning(false);
    }
  };

  const sendLead = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!result || sending) return;
    setFieldErrors({});
    setFormError('');
    setSending(true);
    try {
      const res = await api<{ reference: string; message: string }>(`/audit/${result.token}/lead/`, {
        method: 'POST',
        json: { name: form.name, email: form.email, phone: form.phone, message: form.message, consent: form.consent, website: form.website },
      });
      setSentRef(res.reference || 'sent');
    } catch (err) {
      if (err instanceof ApiError) {
        const fe: Record<string, string> = {};
        Object.entries(err.details || {}).forEach(([k, v]) => { fe[k] = Array.isArray(v) ? v[0] : v; });
        setFieldErrors(fe);
        setFormError(Object.keys(fe).length ? '' : err.message);
      } else {
        setFormError('Something went wrong. Please try again.');
      }
    } finally {
      setSending(false);
    }
  };

  const lvl = result?.level ? levelText[result.level] : undefined;
  const failed = result?.checks.filter((c) => !c.ok).length ?? 0;

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      <section className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-8 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-6">
          <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
          <span>Free · Takes about 20 seconds</span>
        </div>
        <h1 className="fluid-h1 font-extrabold text-white font-display">
          Is your website <span className="text-gradient">losing you customers?</span>
        </h1>
        <p className="mt-6 text-base sm:text-lg text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          Enter your website address. We check security, mobile friendliness, search basics, instant-chat buttons and broken links, then show you exactly what to fix.
        </p>

        <form onSubmit={runAudit} className="mt-10 max-w-2xl mx-auto flex flex-col sm:flex-row gap-3" noValidate>
          <label htmlFor="audit-url" className="sr-only">Your website address</label>
          <input
            id="audit-url"
            type="text"
            inputMode="url"
            autoComplete="url"
            autoCapitalize="none"
            spellCheck={false}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="yourbusiness.com"
            aria-invalid={!!urlError}
            aria-describedby={urlError ? 'audit-url-error' : undefined}
            className={`${inputCls} sm:flex-1`}
            disabled={running}
          />
          <Button type="submit" size="lg" isLoading={running} leftIcon={<Search className="w-4 h-4" />}>
            {running ? 'Checking…' : 'Check my website'}
          </Button>
        </form>
        {urlError && (
          <p id="audit-url-error" role="alert" className="mt-3 text-sm text-rose-400 flex items-center justify-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" /> {urlError}
          </p>
        )}
        <p className="mt-4 text-xs text-aub-text-secondary flex items-center justify-center gap-1.5">
          <Lock className="w-3.5 h-3.5" /> We only read your public home page and a few of its links. Nothing is stored about you unless you ask us to get in touch.
        </p>
      </section>

      <div ref={resultRef} className="scroll-mt-28" />

      {result && !result.reachable && (
        <section className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <GlassCard className="p-6 sm:p-8 text-center border-amber-500/40">
            <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-3" />
            <h2 className="text-xl font-bold text-white font-display">We couldn’t open that website</h2>
            <p className="mt-2 text-sm text-aub-text-secondary">{result.error || 'The site did not respond. Check the address and try again.'}</p>
            <p className="mt-2 text-xs text-aub-text-secondary">No score is shown when a site cannot be reached, so we never guess.</p>
          </GlassCard>
        </section>
      )}

      {result && result.reachable && result.health !== null && (
        <motion.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 space-y-8" aria-live="polite">
          <GlassCard className="p-6 sm:p-8">
            <div className="flex flex-col sm:flex-row items-center gap-6 sm:gap-10">
              <ScoreRing score={result.health} colour={lvl?.colour || '#7B2FFF'} />
              <div className="text-center sm:text-left min-w-0">
                <p className="text-xs uppercase tracking-wider text-aub-accent-labels">Website health score</p>
                <h2 className="mt-1 text-2xl sm:text-3xl font-extrabold text-white font-display">{lvl?.label || 'Audit complete'}</h2>
                <p className="mt-2 text-sm text-aub-text-secondary break-all">{result.url}</p>
                <p className="mt-3 text-sm text-aub-text-secondary flex flex-wrap items-center justify-center sm:justify-start gap-x-5 gap-y-1">
                  <span className="inline-flex items-center gap-1.5"><XCircle className="w-4 h-4 text-rose-400" /> {failed} {failed === 1 ? 'issue' : 'issues'} found</span>
                  {result.loadSeconds !== null && <span className="inline-flex items-center gap-1.5"><Gauge className="w-4 h-4 text-aub-purple" /> Loaded in {result.loadSeconds.toFixed(1)}s</span>}
                </p>
              </div>
            </div>
          </GlassCard>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <GlassCard className="p-6 sm:p-8">
              <h3 className="text-lg font-bold text-white font-display mb-4">What we checked</h3>
              <ul className="space-y-3">
                {result.checks.map((c) => (
                  <li key={c.key} className="flex items-start gap-3 text-sm">
                    {c.ok ? <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" aria-label="Passed" /> : <XCircle className="w-5 h-5 text-rose-400 shrink-0" aria-label="Needs work" />}
                    <span className={c.ok ? 'text-aub-text-secondary' : 'text-white font-medium'}>{c.label}</span>
                  </li>
                ))}
              </ul>
            </GlassCard>

            <GlassCard className="p-6 sm:p-8">
              <h3 className="text-lg font-bold text-white font-display mb-4">What to fix first</h3>
              {result.findings.length === 0 ? (
                <p className="text-sm text-aub-text-secondary">Nothing urgent found on the pages we checked. Nice work.</p>
              ) : (
                <ul className="space-y-4">
                  {result.findings.map((f, i) => (
                    <li key={i} className="text-sm">
                      <p className="font-semibold text-white">{f.title}</p>
                      <p className="mt-1 text-aub-text-secondary leading-relaxed">{f.detail}</p>
                      {f.fix && <p className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-aub-accent-labels"><Wrench className="w-3.5 h-3.5" /> We can help with: {f.fix}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </GlassCard>
          </div>

          <GlassCard className="p-6 sm:p-8 border-aub-purple/40">
            {sentRef ? (
              <div className="text-center py-4" role="status">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
                <h3 className="text-xl font-bold text-white font-display">Thank you — we’ve got your request</h3>
                <p className="mt-2 text-sm text-aub-text-secondary">
                  A specialist will review your audit and contact you very soon.{sentRef !== 'sent' && <> Your reference is <strong className="text-white">{sentRef}</strong>.</>}
                </p>
                {wa && <a href={wa} target="_blank" rel="noopener noreferrer" className="inline-flex mt-4 text-sm text-aub-accent-labels hover:text-white transition-colors">Prefer WhatsApp? Message us directly <ArrowRight className="w-4 h-4 ml-1.5 self-center" /></a>}
              </div>
            ) : (
              <>
                <h3 className="text-xl sm:text-2xl font-bold text-white font-display">Want us to fix these for you?</h3>
                <p className="mt-2 text-sm text-aub-text-secondary">Leave your details and a specialist will go through this audit with you. No obligation.</p>
                <form onSubmit={sendLead} className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4" noValidate>
                  <div>
                    <label htmlFor="al-name" className="block text-xs font-semibold text-aub-text-secondary mb-1.5">Your name</label>
                    <input id="al-name" className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoComplete="name" aria-invalid={!!fieldErrors.name} />
                    {fieldErrors.name && <p role="alert" className="mt-1 text-xs text-rose-400">{fieldErrors.name}</p>}
                  </div>
                  <div>
                    <label htmlFor="al-email" className="block text-xs font-semibold text-aub-text-secondary mb-1.5">Email</label>
                    <input id="al-email" type="email" className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="email" aria-invalid={!!fieldErrors.email} />
                    {fieldErrors.email && <p role="alert" className="mt-1 text-xs text-rose-400">{fieldErrors.email}</p>}
                  </div>
                  <div className="sm:col-span-2">
                    <label htmlFor="al-phone" className="block text-xs font-semibold text-aub-text-secondary mb-1.5">Phone / WhatsApp (optional, include country code)</label>
                    <input id="al-phone" type="tel" className={inputCls} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} autoComplete="tel" placeholder="+92 300 1234567" />
                  </div>
                  <div className="sm:col-span-2">
                    <label htmlFor="al-msg" className="block text-xs font-semibold text-aub-text-secondary mb-1.5">Anything we should know? (optional)</label>
                    <textarea id="al-msg" rows={3} className={inputCls} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} maxLength={1000} />
                  </div>
                  {/* honeypot: real visitors never see or fill this */}
                  <div aria-hidden="true" style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, overflow: 'hidden' }}>
                    <label htmlFor="al-website">Leave this empty</label>
                    <input id="al-website" tabIndex={-1} autoComplete="off" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="flex items-start gap-3 text-sm text-aub-text-secondary cursor-pointer">
                      <input type="checkbox" className="mt-1 w-4 h-4 accent-[#EC008C]" checked={form.consent} onChange={(e) => setForm({ ...form, consent: e.target.checked })} aria-invalid={!!fieldErrors.consent} />
                      <span>I agree that {site.siteName || 'AUB SQUARE'} may contact me about this audit using the details above.</span>
                    </label>
                    {fieldErrors.consent && <p role="alert" className="mt-1 text-xs text-rose-400">{fieldErrors.consent}</p>}
                  </div>
                  {formError && <p role="alert" className="sm:col-span-2 text-sm text-rose-400">{formError}</p>}
                  <div className="sm:col-span-2">
                    <Button type="submit" size="lg" isLoading={sending} rightIcon={<ArrowRight className="w-4 h-4" />} className="w-full sm:w-auto">
                      Get my free action plan
                    </Button>
                  </div>
                </form>
              </>
            )}
          </GlassCard>
        </motion.section>
      )}
    </div>
  );
};

export default FreeAuditPage;
