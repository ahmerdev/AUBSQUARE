import React from 'react';
import { motion } from 'framer-motion';
import { 
  Sparkles, 
  Phone, 
  Mail, 
  MapPin, 
  Clock, 
  MessageSquare, 
  ArrowRight,
  Globe2,
  CheckCircle2
} from 'lucide-react';
import { SectionHeading } from '../components/ui/SectionHeading';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { Link } from 'react-router-dom';
import { useModal } from '../context/ModalContext';
import { useSite, whatsappLink } from '../context/CmsContext';

export const ContactPage: React.FC = () => {
  const { openQuoteModal } = useModal();
  const site = useSite();
  const wa = whatsappLink(site);

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* 1. HERO */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-12 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-6">
          <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
          <span>Get in Touch</span>
        </div>

        <h1 className="fluid-h1 font-extrabold text-white font-display max-w-4xl mx-auto">
          Let’s Build Something <span className="text-gradient">Iconic Together.</span>
        </h1>

        <p className="mt-6 text-base sm:text-lg text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          Whether you are launching a new company from scratch or preparing for a national rebrand, our founders are ready to advise you.
        </p>
      </section>

      {/* 2. CONTACT CHANNELS & PROMPT TO OPEN MODAL */}
      <section className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Column: Direct Founder Channels */}
          <div className="lg:col-span-6 space-y-6">
            <GlassCard className="p-8 border-aub-purple/40 space-y-6">
              <h2 className="text-2xl font-bold text-white font-display">Direct Agency Channels</h2>
              
              <div className="space-y-4">
                {/* WhatsApp */}
                {wa && <a
                  href={wa}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-4 p-4 rounded-2xl bg-aub-card/80 border border-aub-border hover:border-[#25D366] transition-all group"
                >
                  <div className="w-12 h-12 rounded-xl bg-[#25D366]/20 border border-[#25D366]/40 flex items-center justify-center text-[#25D366] shrink-0 group-hover:scale-105 transition-transform">
                    <Phone className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-aub-text-secondary">Official WhatsApp</span>
                    <h3 className="text-base font-bold text-white mt-0.5">{site.phone || 'Message us on WhatsApp'}</h3>
                    <p className="text-xs text-aub-accent-labels mt-1">Instant voice & text chat with agency founders.</p>
                  </div>
                </a>}

                {/* Email */}
                {site.contactEmail && <a
                  href={`mailto:${site.contactEmail}`}
                  className="flex items-start gap-4 p-4 rounded-2xl bg-aub-card/80 border border-aub-border hover:border-aub-magenta transition-all group"
                >
                  <div className="w-12 h-12 rounded-xl bg-aub-magenta/20 border border-aub-magenta/40 flex items-center justify-center text-aub-magenta shrink-0 group-hover:scale-105 transition-transform">
                    <Mail className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-aub-text-secondary">Official Email</span>
                    <h3 className="text-base font-bold text-white mt-0.5 break-all">{site.contactEmail}</h3>
                    <p className="text-xs text-aub-accent-labels mt-1">Detailed proposals & formal RFQ specifications.</p>
                  </div>
                </a>}

                {site.address && (
                  <div className="flex items-start gap-4 p-4 rounded-2xl bg-aub-card/50 border border-aub-border">
                    <div className="w-12 h-12 rounded-xl bg-aub-magenta/20 border border-aub-magenta/40 flex items-center justify-center text-aub-magenta shrink-0"><MapPin className="w-6 h-6" /></div>
                    <div>
                      <span className="text-xs font-semibold uppercase tracking-wider text-aub-text-secondary">Studio</span>
                      <p className="text-sm font-bold text-white mt-0.5 whitespace-pre-line">{site.address}</p>
                    </div>
                  </div>
                )}

                {/* Availability */}
                {site.businessHours && <div className="flex items-start gap-4 p-4 rounded-2xl bg-aub-card/50 border border-aub-border">
                  <div className="w-12 h-12 rounded-xl bg-aub-purple/20 border border-aub-purple/40 flex items-center justify-center text-aub-purple shrink-0">
                    <Clock className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-aub-text-secondary">Operating Hours</span>
                    <h3 className="text-base font-bold text-white mt-0.5 whitespace-pre-line">{site.businessHours}</h3>
                  </div>
                </div>}
              </div>
            </GlassCard>
          </div>

          {/* Right Column: Trigger Quote Modal Box */}
          <div className="lg:col-span-6">
            <GlassCard className="p-8 sm:p-12 border-aub-magenta/40 text-center space-y-6 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-aub-magenta/15 rounded-full blur-3xl pointer-events-none" />

              <div className="w-16 h-16 rounded-2xl bg-aub-gradient flex items-center justify-center mx-auto text-white shadow-glow-magenta">
                <MessageSquare className="w-8 h-8" />
              </div>

              <div>
                <h3 className="text-2xl sm:text-3xl font-bold text-white font-display">
                  Request a Formal Project Proposal
                </h3>
                <p className="text-sm text-aub-text-secondary mt-2 leading-relaxed">
                  Click the button below to open our interactive quote questionnaire. Tell us your deliverables and budget, and we’ll formulate a clear project roadmap within 24 hours.
                </p>
              </div>

              <div className="pt-2">
                <Button
                  variant="gradient"
                  size="lg"
                  className="w-full sm:w-auto"
                  onClick={() => openQuoteModal()}
                  rightIcon={<ArrowRight className="w-5 h-5" />}
                >
                  Send Us a Message
                </Button>
              </div>

              <div className="pt-4 border-t border-aub-border/60 text-xs text-aub-accent-labels space-y-1">
                <p>✓ No commitments · 100% Free Consultation</p>
                <p>✓ All discussions protected under strict confidentiality</p>
                <p className="pt-2 text-aub-text-secondary">Not ready to talk yet? <Link to="/free-audit" className="text-white underline underline-offset-4 hover:text-aub-magenta">Get a free website audit</Link>.</p>
              </div>
            </GlassCard>
          </div>
        </div>
      </section>
    </div>
  );
};
