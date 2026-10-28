import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Sparkles, 
  Palette, 
  Layout, 
  Code, 
  Share2, 
  CheckCircle2, 
  ArrowRight,
  ShieldCheck,
  Zap,
  Layers
} from 'lucide-react';
import { SectionHeading } from '../components/ui/SectionHeading';
import { StickyStack, StickyCard } from '../components/ui/StickyCard';
import { Button } from '../components/ui/Button';
import { useServices } from '../context/CmsContext';
import { useModal } from '../context/ModalContext';

export const ServicesPage: React.FC = () => {
  const { openQuoteModal } = useModal();
  const servicesData = useServices();

  const serviceIconMap: Record<string, React.ReactNode> = {
    'Sparkles': <Sparkles className="w-6 h-6 text-aub-magenta" />,
    'Palette': <Palette className="w-6 h-6 text-aub-purple" />,
    'Layout': <Layout className="w-6 h-6 text-aub-accent-labels" />,
    'Code': <Code className="w-6 h-6 text-aub-magenta" />,
    'Share2': <Share2 className="w-6 h-6 text-aub-purple" />,
  };

  return (
    <div className="relative pt-20 sm:pt-24 pb-28">
      {/* 1. HERO */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-10 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-5 shadow-md">
          <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
          <span>Interactive Stacked Services Deck</span>
        </div>

        <h1 className="fluid-h1 font-extrabold text-white font-display max-w-4xl mx-auto">
          Everything Your Brand Needs to <span className="text-gradient">Dominate Its Market.</span>
        </h1>

        <p className="mt-4 sm:mt-5 text-sm sm:text-base text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          Scroll down through our five core creative disciplines. Each service card pins and stacks dynamically as you explore our capabilities.
        </p>
      </section>

      {/* 2. STICKY STACKED SERVICES DECK (PERFECT VIEWPORT FIT, NO CUT-OFF) */}
      <section className="relative max-w-5xl mx-auto px-3 sm:px-6 lg:px-8 py-4">
        <StickyStack>
          {servicesData.map((service, index) => (
            <StickyCard
              key={service.id}
              index={index}
              totalCards={servicesData.length}
              className={`rounded-2xl sm:rounded-3xl border border-aub-border/90 p-4 sm:p-6 lg:p-7 shadow-2xl shadow-black/95 backdrop-blur-2xl relative group ${
                service.isPrimary
                  ? 'bg-gradient-to-br from-[#1F173D] via-[#150F2B] to-[#0B0B12] border-aub-magenta/50'
                  : 'bg-gradient-to-br from-[#191430] via-[#120D24] to-[#0B0B12]'
              }`}
            >
              {/* Card Ambient Glows */}
              <div className="absolute top-0 right-0 w-72 h-72 bg-aub-magenta/15 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute bottom-0 left-0 w-72 h-72 bg-aub-purple/20 rounded-full blur-3xl pointer-events-none" />

              {/* Service Number & Discipline Tag */}
              <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-aub-border/60 mb-4 sm:mb-5 relative z-10">
                <div className="flex items-center gap-2.5 sm:gap-3">
                  <span className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-aub-card border border-aub-border flex items-center justify-center text-xs font-mono font-bold text-aub-magenta shrink-0">
                    0{index + 1}
                  </span>
                  <div>
                    <h2 className="text-lg sm:text-xl font-bold text-white font-display leading-tight">
                      {service.title}
                    </h2>
                    <span className="text-[10px] text-aub-accent-labels font-semibold uppercase tracking-wider block">
                      Core Agency Discipline
                    </span>
                  </div>
                </div>

                {service.isPrimary && (
                  <span className="px-2.5 py-1 rounded-full bg-aub-magenta/20 border border-aub-magenta/40 text-aub-magenta text-[10px] sm:text-xs font-bold uppercase tracking-wider shadow-glow-magenta/20">
                    ★ Signature
                  </span>
                )}
              </div>

              {/* Main Content Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-7 items-start relative z-10">
                {/* Left Column: Description, Benefits & Process (7 cols) */}
                <div className="lg:col-span-7 space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl bg-aub-card border border-aub-border flex items-center justify-center shadow-lg shrink-0 mt-0.5">
                      {serviceIconMap[service.iconName] || <Sparkles className="w-5 h-5 text-aub-magenta" />}
                    </div>
                    <p className="text-xs sm:text-sm text-aub-text-secondary leading-relaxed">
                      {service.fullDescription}
                    </p>
                  </div>

                  {/* Strategic Benefits */}
                  {service.benefits.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-aub-accent-labels">
                      Strategic Advantages:
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {service.benefits.map((b, bIdx) => (
                        <div key={bIdx} className="flex items-start gap-1.5 text-xs text-white">
                          <CheckCircle2 className="w-3.5 h-3.5 text-aub-magenta shrink-0 mt-0.5" />
                          <span className="leading-snug">{b}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  )}

                  {/* 4-Step Process Strip */}
                  {service.process.length > 0 && (
                  <div className="pt-1">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-aub-accent-labels mb-2">
                      Execution Milestones:
                    </h4>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {service.process.map(step => (
                        <div key={step.step} className="p-2 sm:p-2.5 rounded-xl bg-aub-card/80 border border-aub-border/80">
                          <span className="text-[10px] font-mono font-bold text-aub-magenta">{step.step}</span>
                          <h5 className="text-[11px] font-bold text-white font-display mt-0.5 truncate">{step.title}</h5>
                          <p className="text-[9px] text-aub-text-secondary mt-0.5 leading-tight line-clamp-2">{step.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  )}

                  {/* Action Buttons */}
                  <div className="pt-2 flex flex-wrap items-center gap-3">
                    <Button
                      variant="gradient"
                      size="sm"
                      onClick={() => openQuoteModal(service.title)}
                      rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                    >
                      Start {service.title} Project
                    </Button>
                    <Link to={`/services/${service.slug || service.id}`} className="text-xs font-semibold text-aub-accent-labels hover:text-white transition-colors">
                      Full service details →
                    </Link>
                    <Link to="/portfolio" className="text-xs font-semibold text-aub-text-secondary hover:text-white transition-colors">
                      View Portfolio Work →
                    </Link>
                  </div>
                </div>

                {/* Right Column: Deliverables Card Box (5 cols) */}
                <div className="lg:col-span-5">
                  <div className="rounded-xl sm:rounded-2xl bg-[#0F0B1E]/90 border border-aub-border/90 p-4 sm:p-5 space-y-3 shadow-xl">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs sm:text-sm font-bold text-white font-display flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
                        <span>Guaranteed Deliverables</span>
                      </h3>
                      <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono font-semibold border border-emerald-500/30">
                        100% Vector IP
                      </span>
                    </div>

                    <p className="text-[11px] text-aub-text-secondary">
                      Comprehensive master source assets delivered on completion:
                    </p>

                    <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 gap-1.5 pt-1">
                      {service.deliverables.map((del, dIdx) => (
                        <li key={dIdx} className="flex items-start gap-2 text-xs text-aub-text-primary">
                          <span className="w-1.5 h-1.5 rounded-full bg-aub-magenta shrink-0 mt-1.5" />
                          <span className="leading-snug">{del}</span>
                        </li>
                      ))}
                    </ul>

                    <div className="pt-2.5 border-t border-aub-border/60 text-[10px] text-aub-accent-labels font-medium flex items-center gap-1.5">
                      <ShieldCheck className="w-3.5 h-3.5 text-aub-purple shrink-0" />
                      <span>Full commercial & IP copyright ownership transfer.</span>
                    </div>
                  </div>
                </div>
              </div>
            </StickyCard>
          ))}
        </StickyStack>
      </section>

      {/* 3. FINAL BOTTOM CTA */}
      <section className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 text-center">
        <div className="p-8 sm:p-10 rounded-3xl glass-panel border border-aub-purple/50 shadow-2xl">
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">
            Not Sure Which Discipline Fits Your Scope?
          </h2>
          <p className="text-xs sm:text-sm text-aub-text-secondary max-w-lg mx-auto mb-6 leading-relaxed">
            Message us with your current website link or brand deck. Our founders will review your materials and recommend an exact roadmap.
          </p>
          <Button variant="gradient" size="md" onClick={() => openQuoteModal()}>
            Request Free Brand Audit & Quote
          </Button>
        </div>
      </section>
    </div>
  );
};
