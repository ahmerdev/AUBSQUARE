import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles, CheckCircle2, AlertCircle, Phone, Send, ArrowRight } from 'lucide-react';
import confetti from 'canvas-confetti';
import { useModal } from '../../context/ModalContext';
import { QuoteFormData } from '../../types';
import { useScrollLock } from '../../hooks/useScrollLock';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { useDeviceProfile } from '../../lib/device';
import { useCms, useSite, whatsappLink, useServices } from '../../context/CmsContext';
import { api, ApiError } from '../../lib/api';

const countryCodes = [
  { code: '+92', country: 'PK (+92)' },
  { code: '+1', country: 'US/CA (+1)' },
  { code: '+44', country: 'UK (+44)' },
  { code: '+971', country: 'UAE (+971)' },
  { code: '+966', country: 'SA (+966)' },
  { code: '+49', country: 'DE (+49)' },
  { code: '+61', country: 'AU (+61)' },
];

const fallbackBudgets = [
  { label: '$500 - $1,500', value: '500-1500' },
  { label: '$1,500 - $3,000', value: '1500-3000' },
  { label: '$3,000 - $5,000', value: '3000-5000' },
  { label: '$5,000+ (Enterprise Scope)', value: '5000-plus' },
];

export const QuoteModal: React.FC = () => {
  const { isQuoteModalOpen, closeQuoteModal, selectedService } = useModal();

  const { data } = useCms();
  const site = useSite();
  const services = useServices();
  const cfg = data?.form;
  const servicesList = (cfg?.serviceOptions?.length ? cfg.serviceOptions : services.map(s => s.title));
  const budgetRanges = cfg?.budgetOptions?.length ? cfg.budgetOptions : fallbackBudgets;
  const requirePhone = cfg?.requirePhone ?? true;
  const requireService = cfg?.requireService ?? true;
  const requireBudget = cfg?.requireBudget ?? true;
  const consentRequired = cfg?.consentRequired ?? false;

  const [formData, setFormData] = useState<QuoteFormData>({
    name: '',
    email: '',
    whatsapp: '',
    countryCode: '+92',
    service: selectedService || '',
    budget: '',
    message: '',
  });
  const [consent, setConsent] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [website, setWebsite] = useState(''); // honeypot: real visitors never see or fill this
  const [formToken, setFormToken] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState<{ title: string; message: string; reference: string } | null>(null);

  const [errors, setErrors] = useState<Partial<Record<keyof QuoteFormData | 'consent', string>>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  // A fresh anti-spam token every time the form is opened (the server rejects instant, bot-speed submissions).
  useEffect(() => {
    if (!isQuoteModalOpen) return;
    setSubmitError('');
    api<{ token: string }>('/form-token/').then(r => setFormToken(r.token)).catch(() => setFormToken(''));
  }, [isQuoteModalOpen]);

  // Sync selected service when modal opens with preselected service
  useEffect(() => {
    if (selectedService) {
      setFormData(prev => ({ ...prev, service: selectedService }));
    }
  }, [selectedService]);

  const dialogRef = useRef<HTMLDivElement>(null);
  const { isMobile, reducedMotion } = useDeviceProfile();

  useScrollLock(isQuoteModalOpen);
  useFocusTrap(dialogRef, isQuoteModalOpen);

  // Reset success state each time the modal closes
  useEffect(() => {
    if (!isQuoteModalOpen) setIsSuccess(false);
  }, [isQuoteModalOpen]);

  // Escape key handler (only while open)
  useEffect(() => {
    if (!isQuoteModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeQuoteModal();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isQuoteModalOpen, closeQuoteModal]);

  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof QuoteFormData | "consent", string>> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Please enter your full name.';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!formData.whatsapp.trim()) {
      if (requirePhone) newErrors.whatsapp = 'WhatsApp number is required for fast project coordination.';
    } else if (formData.whatsapp.replace(/\D/g, '').length < 7) {
      newErrors.whatsapp = 'Please enter a valid phone number.';
    }

    if (requireService && !formData.service) newErrors.service = 'Please choose a service.';
    if (requireBudget && !formData.budget) newErrors.budget = 'Please choose a budget range.';

    if (formData.message.trim().length < 10) {
      newErrors.message = 'Please tell us a little more about your project (at least 10 characters).';
    }
    if (consentRequired && !consent) newErrors.consent = 'Please accept to continue.';

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) {
      requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
      return;
    }

    setIsSubmitting(true);
    setSubmitError('');

    try {
      let token = formToken;
      if (!token) token = (await api<{ token: string }>('/form-token/')).token;
      const q = new URLSearchParams(window.location.search);
      const res = await api<{ reference: string; title: string; message: string }>('/leads/', {
        method: 'POST',
        json: {
          name: formData.name,
          email: formData.email,
          countryCode: formData.countryCode,
          phone: formData.whatsapp.trim(),
          service: formData.service,
          budget: formData.budget,
          message: formData.message,
          consent,
          marketingConsent: marketing,
          website,
          formToken: token,
          page: window.location.pathname,
          source: 'quote_modal',
          utm_source: q.get('utm_source') || '',
          utm_medium: q.get('utm_medium') || '',
          utm_campaign: q.get('utm_campaign') || '',
        },
      });
      setResult(res);
      setIsSuccess(true);
      confetti({
        particleCount: 80,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#EC008C', '#7B2FFF', '#C99BFF', '#FFFFFF'],
      });
    } catch (err) {
      const ae = err as ApiError;
      if (ae.details) {
        const map: Record<string, string> = {};
        Object.entries(ae.details).forEach(([k, v]) => { map[k === 'phone' ? 'whatsapp' : k] = Array.isArray(v) ? v[0] : String(v); });
        setErrors(map);
        requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
      }
      setSubmitError(ae.details ? 'Please correct the highlighted fields.' : ae.message || cfg?.errorMessage || 'Something went wrong. Please try again or WhatsApp us.');
      api<{ token: string }>('/form-token/').then(r => setFormToken(r.token)).catch(() => {});
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleWhatsAppDirect = () => {
    const text = encodeURIComponent(
      `Hello AUB SQUARE! My name is ${formData.name || 'a client'}. I am interested in ${formData.service} for my project. Budget: ${formData.budget}. Message: ${formData.message}`
    );
    const link = whatsappLink(site, decodeURIComponent(text));
    if (link) window.open(link, '_blank', 'noopener');
  };

  return (
    <AnimatePresence>
      {isQuoteModalOpen && (
        <div className="fixed inset-0 z-[55] flex items-end sm:items-center justify-center sm:p-6">
          {/* Dimmed Blurred Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={closeQuoteModal}
            className="fixed inset-0 bg-black/80 backdrop-blur-md"
            aria-hidden="true"
          />

          {/* Dialog Modal Surface */}
          <motion.div
            ref={dialogRef}
            tabIndex={-1}
            data-lenis-prevent
            initial={isMobile ? { y: '100%' } : { opacity: 0, scale: 0.95, y: 20 }}
            animate={isMobile ? { y: 0 } : { opacity: 1, scale: 1, y: 0 }}
            exit={isMobile ? { y: '100%' } : { opacity: 0, scale: 0.95, y: 20 }}
            transition={reducedMotion ? { duration: 0.01 } : { type: 'spring', damping: 30, stiffness: 320 }}
            className="relative z-10 w-full sm:max-w-xl max-h-[94dvh] sm:max-h-[90dvh] overflow-y-auto overscroll-contain rounded-t-[28px] sm:rounded-3xl bg-[#120D24] border border-aub-border/90 border-b-0 sm:border-b px-4 xs:px-5 pt-3 sm:pt-8 sm:px-8 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:pb-8 shadow-2xl outline-none"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-headline"
          >
            {/* Mobile drag-handle affordance */}
            <div className="sm:hidden mx-auto mb-3 h-1.5 w-12 rounded-full bg-aub-border/90" aria-hidden="true" />
            {/* Ambient Background Gradient Glow */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-aub-magenta/10 rounded-full blur-3xl pointer-events-none" />
            <div className="absolute bottom-0 left-0 w-64 h-64 bg-aub-purple/15 rounded-full blur-3xl pointer-events-none" />

            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-aub-border/60 relative z-10">
              <div>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold text-aub-accent-labels uppercase tracking-wider mb-2">
                  <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
                  <span>Start Your Transformation</span>
                </div>
                <h3 id="modal-headline" className="text-2xl sm:text-3xl font-bold text-white font-display">
                  Get a Free <span className="text-gradient">Quote</span>
                </h3>
                <p className="text-xs sm:text-sm text-aub-text-secondary mt-1">
                  Tell us about your project. Founder Muhammad Bilal will review and respond within 24 hours.
                </p>
              </div>

              <button
                onClick={closeQuoteModal}
                className="w-11 h-11 rounded-full bg-aub-card border border-aub-border flex items-center justify-center text-aub-text-secondary hover:text-white hover:border-aub-magenta/60 transition-colors shrink-0"
                aria-label="Close modal"
                data-autofocus
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content: Success View vs. Form View */}
            <div className="mt-6 relative z-10">
              {isSuccess ? (
                <div className="py-8 text-center space-y-5">
                  <div className="w-16 h-16 rounded-full bg-green-500/20 border border-green-500/40 text-green-400 mx-auto flex items-center justify-center shadow-lg">
                    <CheckCircle2 className="w-8 h-8" />
                  </div>
                  <div>
                    <h4 className="text-2xl font-bold text-white font-display">
                      {result?.title || cfg?.successTitle || 'Request received'}
                    </h4>
                    <p className="text-sm text-aub-text-secondary mt-2 max-w-md mx-auto leading-relaxed">
                      {result?.message || cfg?.successMessage || 'Thank you. Our team will contact you shortly.'}
                    </p>
                    {result?.reference && <p className="text-xs text-aub-text-secondary mt-2">Reference: <span className="text-white font-mono">{result.reference}</span></p>}
                  </div>

                  <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
                    {whatsappLink(site) && <button
                      onClick={handleWhatsAppDirect}
                      className="px-6 py-3 rounded-full bg-[#25D366] hover:bg-[#20bd5a] text-black font-bold text-sm flex items-center justify-center gap-2 transition-transform hover:scale-105"
                    >
                      <Phone className="w-4 h-4" />
                      <span>Chat on WhatsApp Directly</span>
                    </button>}
                    <button
                      onClick={closeQuoteModal}
                      className="px-6 py-3 rounded-full glass-panel text-white font-semibold text-sm hover:bg-white/10"
                    >
                      Close Window
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  {/* Name Field */}
                  <div>
                    <label htmlFor="qm-name" className="block text-xs font-semibold uppercase tracking-wider text-aub-text-secondary mb-1.5">
                      Your Full Name <span className="text-aub-magenta">*</span>
                    </label>
                    <input
                      id="qm-name" name="name" autoComplete="name" aria-invalid={!!errors.name}
                      type="text"
                      placeholder="e.g. David Sterling"
                      value={formData.name}
                      onChange={e => setFormData({ ...formData, name: e.target.value })}
                      className={`w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border text-white placeholder-white/30 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-aub-magenta transition-all ${
                        errors.name ? 'border-red-500' : 'border-aub-border'
                      }`}
                    />
                    {errors.name && (
                      <p role="alert" className="text-red-400 text-xs mt-1 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" />
                        {errors.name}
                      </p>
                    )}
                  </div>

                  {/* Email & WhatsApp Two Columns */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="qm-email" className="block text-xs font-semibold uppercase tracking-wider text-aub-text-secondary mb-1.5">
                        Your Email <span className="text-aub-magenta">*</span>
                      </label>
                      <input
                        id="qm-email" name="email" autoComplete="email" inputMode="email" aria-invalid={!!errors.email}
                        type="email"
                        placeholder="david@company.com"
                        value={formData.email}
                        onChange={e => setFormData({ ...formData, email: e.target.value })}
                        className={`w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border text-white placeholder-white/30 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-aub-magenta transition-all ${
                          errors.email ? 'border-red-500' : 'border-aub-border'
                        }`}
                      />
                      {errors.email && (
                        <p role="alert" className="text-red-400 text-xs mt-1 flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" />
                          {errors.email}
                        </p>
                      )}
                    </div>

                    <div>
                      <label htmlFor="qm-phone" className="block text-xs font-semibold uppercase tracking-wider text-aub-text-secondary mb-1.5">
                        WhatsApp Number {requirePhone && <span className="text-aub-magenta">*</span>}
                      </label>
                      <div className="flex gap-2">
                        <select
                          aria-label="Country code"
                          value={formData.countryCode}
                          onChange={e => setFormData({ ...formData, countryCode: e.target.value })}
                          className="w-28 shrink-0 px-2 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border border-aub-border text-white text-base sm:text-xs focus:outline-none focus:ring-2 focus:ring-aub-magenta"
                        >
                          {countryCodes.map(c => (
                            <option key={c.code} value={c.code} className="bg-[#120D24] text-white">
                              {c.country}
                            </option>
                          ))}
                        </select>
                        <input
                          id="qm-phone" name="whatsapp" autoComplete="tel-national" inputMode="tel" aria-invalid={!!errors.whatsapp}
                          type="tel"
                          placeholder="327 2755118"
                          value={formData.whatsapp}
                          onChange={e => setFormData({ ...formData, whatsapp: e.target.value })}
                          className={`w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border text-white placeholder-white/30 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-aub-magenta transition-all ${
                            errors.whatsapp ? 'border-red-500' : 'border-aub-border'
                          }`}
                        />
                      </div>
                      {errors.whatsapp && (
                        <p role="alert" className="text-red-400 text-xs mt-1 flex items-center gap-1">
                          <AlertCircle className="w-3.5 h-3.5" />
                          {errors.whatsapp}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Service & Budget Two Columns */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="qm-service" className="block text-xs font-semibold uppercase tracking-wider text-aub-text-secondary mb-1.5">
                        Service Needed
                      </label>
                      <select
                        id="qm-service" aria-invalid={!!errors.service}
                        value={formData.service}
                        onChange={e => setFormData({ ...formData, service: e.target.value })}
                        className="w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border border-aub-border text-white text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-aub-magenta"
                      >
                        <option value="" className="bg-[#120D24] text-white">Select a service…</option>
                        {(formData.service && !servicesList.includes(formData.service) ? [formData.service, ...servicesList] : servicesList).map(s => (
                          <option key={s} value={s} className="bg-[#120D24] text-white">
                            {s}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label htmlFor="qm-budget" className="block text-xs font-semibold uppercase tracking-wider text-aub-text-secondary mb-1.5">
                        Estimated Budget (USD)
                      </label>
                      <select
                        id="qm-budget" aria-invalid={!!errors.budget}
                        value={formData.budget}
                        onChange={e => setFormData({ ...formData, budget: e.target.value })}
                        className="w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border border-aub-border text-white text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-aub-magenta"
                      >
                        <option value="" className="bg-[#120D24] text-white">Select a range…</option>
                        {budgetRanges.map(b => (
                          <option key={b.value} value={b.value} className="bg-[#120D24] text-white">
                            {b.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {(errors.service || errors.budget) && (
                    <p role="alert" className="text-red-400 text-xs -mt-2 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      {errors.service || errors.budget}
                    </p>
                  )}

                  {/* Message Field */}
                  <div>
                    <label htmlFor="qm-message" className="block text-xs font-semibold uppercase tracking-wider text-aub-text-secondary mb-1.5">
                      Tell Us About Your Project <span className="text-aub-magenta">*</span>
                    </label>
                    <textarea
                      id="qm-message" name="message" aria-invalid={!!errors.message}
                      rows={4}
                      placeholder="Briefly describe your goals, timeline, and vision..."
                      value={formData.message}
                      onChange={e => setFormData({ ...formData, message: e.target.value })}
                      className={`w-full px-4 py-3 min-h-[48px] rounded-xl bg-aub-card/80 border text-white placeholder-white/30 text-base sm:text-sm focus:outline-none focus:ring-2 focus:ring-aub-magenta transition-all resize-none ${
                        errors.message ? 'border-red-500' : 'border-aub-border'
                      }`}
                    />
                    {errors.message && (
                      <p role="alert" className="text-red-400 text-xs mt-1 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" />
                        {errors.message}
                      </p>
                    )}
                  </div>

                  {/* Honeypot (hidden from people and assistive tech) */}
                  <input type="text" name="website" value={website} onChange={e => setWebsite(e.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" />

                  {consentRequired && (
                    <div>
                      <label className="flex items-start gap-2 text-xs text-aub-text-secondary">
                        <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} aria-invalid={!!errors.consent} className="mt-0.5 accent-[#EC008C]" />
                        <span>{cfg?.consentText || 'I agree to be contacted about my enquiry.'}</span>
                      </label>
                      {errors.consent && <p role="alert" className="text-red-400 text-xs mt-1">{errors.consent}</p>}
                    </div>
                  )}
                  {cfg?.marketingOptinEnabled && (
                    <label className="flex items-start gap-2 text-xs text-aub-text-secondary">
                      <input type="checkbox" checked={marketing} onChange={e => setMarketing(e.target.checked)} className="mt-0.5 accent-[#EC008C]" />
                      <span>{cfg.marketingOptinText || 'Send me occasional news and offers. I can unsubscribe at any time.'}</span>
                    </label>
                  )}
                  {submitError && (
                    <p role="alert" className="text-red-300 text-xs flex items-center gap-1.5 p-3 rounded-xl bg-red-500/10 border border-red-500/30">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      {submitError}
                    </p>
                  )}

                  {/* Submit Button & WhatsApp Alternative */}
                  <div className="pt-2 space-y-3">
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full py-4 rounded-full bg-aub-gradient text-white font-bold text-sm sm:text-base shadow-glow-magenta hover:shadow-glow-purple transition-all duration-300 hover:scale-[1.01] active:scale-[0.99] flex items-center justify-center gap-2 disabled:opacity-50"
                    >
                      {isSubmitting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          <span>Submitting Proposal...</span>
                        </>
                      ) : (
                        <>
                          <Send className="w-4 h-4" />
                          <span>Submit Quote Request</span>
                        </>
                      )}
                    </button>

                    {whatsappLink(site) && <div className="flex items-center justify-center gap-2 text-xs text-aub-text-secondary pt-1">
                      <span>Or prefer instant messaging?</span>
                      <button
                        type="button"
                        onClick={handleWhatsAppDirect}
                        className="text-[#25D366] hover:underline font-semibold inline-flex items-center gap-1"
                      >
                        <Phone className="w-3 h-3" />
                        WhatsApp us directly
                      </button>
                    </div>}
                  </div>
                </form>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
