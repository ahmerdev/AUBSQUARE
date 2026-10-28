import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Phone,
  Globe2,
  Users,
  Award,
  Clock,
  Zap,
  TrendingUp,
  Layout,
  Code,
  Palette,
  Share2,
  ShieldCheck,
} from 'lucide-react';
import { HeroScene } from '../components/three/HeroScene';
import { AnimatedHeadline } from '../components/ui/AnimatedHeadline';
import { SectionHeading } from '../components/ui/SectionHeading';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { FeaturedPortfolioSlider } from '../components/home/FeaturedPortfolioSlider';
import { FeaturedCaseStudiesSlider } from '../components/home/FeaturedCaseStudiesSlider';
import { BlogSlider } from '../components/home/BlogSlider';
import { TestimonialsSlider } from '../components/home/TestimonialsSlider';
import { Accordion } from '../components/ui/Accordion';
import { BrandCube } from '../components/three/BrandCube';
import { ProcessOrb } from '../components/three/ProcessOrb';
import { Scroll3DSection } from '../components/ui/Scroll3DSection';
import { useModal } from '../context/ModalContext';
import { useFaqs, useHomeSections, useServices, useSite, useTeam, whatsappLink } from '../context/CmsContext';

type D = Record<string, any>;
const arr = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);
const SECTION = 'relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20';

const serviceIconMap: Record<string, React.ReactNode> = {
  Sparkles: <Sparkles className="w-6 h-6 text-aub-magenta" />,
  Palette: <Palette className="w-6 h-6 text-aub-purple" />,
  Layout: <Layout className="w-6 h-6 text-aub-accent-labels" />,
  Code: <Code className="w-6 h-6 text-aub-magenta" />,
  Share2: <Share2 className="w-6 h-6 text-aub-purple" />,
};

const statIcons: Record<string, React.ComponentType<{ className?: string }>> = { Award, Clock, Zap, Globe2, Users, TrendingUp, ShieldCheck };
const statTones = [
  { box: 'bg-aub-magenta/15 border-aub-magenta/30 text-aub-magenta' },
  { box: 'bg-aub-purple/15 border-aub-purple/30 text-aub-purple' },
  { box: 'bg-aub-accent-purple/15 border-aub-accent-purple/30 text-aub-accent-labels' },
  { box: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' },
];
const whyTones = [
  'bg-aub-magenta/20 border-aub-magenta/40 text-aub-magenta shadow-glow-magenta/20',
  'bg-aub-purple/20 border-aub-purple/40 text-aub-purple shadow-glow-purple/20',
  'bg-aub-accent-purple/20 border-aub-accent-purple/40 text-aub-accent-labels',
  'bg-emerald-500/20 border-emerald-500/40 text-emerald-400',
];
const orbs = [
  { color: '#EC008C', secondaryColor: '#7B2FFF', shape: 'octahedron' },
  { color: '#7B2FFF', secondaryColor: '#EC008C', shape: 'icosahedron' },
  { color: '#9333EA', secondaryColor: '#C026D3', shape: 'torus' },
  { color: '#EC008C', secondaryColor: '#FFFFFF', shape: 'dodecahedron' },
] as const;

const Heading: React.FC<{ d: D }> = ({ d }) => (
  <SectionHeading eyebrow={d.eyebrow} title={d.title} gradientWord={d.gradient_word} subtitle={d.subtitle} />
);

// ---------------------------------------------------------------- sections (rendered in the order set in the dashboard)
const Hero: React.FC<{ d: D }> = ({ d }) => {
  const { openQuoteModal } = useModal();
  return (
    <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-16 md:pb-24">
      <div className="absolute top-10 left-1/3 -translate-x-1/2 w-[90vw] max-w-[600px] aspect-square bg-aub-magenta/15 rounded-full blur-[120px] sm:blur-[160px] pointer-events-none" />
      <div className="absolute top-20 right-0 sm:right-10 w-[80vw] max-w-[500px] aspect-square bg-aub-purple/20 rounded-full blur-[120px] sm:blur-[170px] pointer-events-none" />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-8 items-center">
        <motion.div initial={{ opacity: 0, x: -30 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, ease: 'easeOut' }} className="lg:col-span-7 space-y-6 text-left">
          {d.eyebrow && (
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card/90 border border-aub-border/90 text-[11px] sm:text-xs font-semibold tracking-wider uppercase text-aub-accent-labels shadow-lg backdrop-blur-md">
              <span className="w-2 h-2 rounded-full bg-aub-magenta animate-ping" />
              <span>{d.eyebrow}</span>
            </div>
          )}
          <AnimatedHeadline
            as="h1"
            className="fluid-hero font-extrabold text-white font-display"
            parts={[{ text: d.headline_start || '' }, ...(d.headline_highlight ? [{ text: d.headline_highlight, gradient: true }] : [])]}
          />
          <p className="fluid-lead text-aub-text-secondary max-w-xl">{d.description}</p>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4 pt-2">
            <Button variant="gradient" size="lg" onClick={() => openQuoteModal()} leftIcon={<Sparkles className="w-5 h-5" />}>
              {d.cta_primary_label || 'Get a Free Quote'}
            </Button>
            {d.cta_secondary_label && (
              <Link to={d.cta_secondary_url || '/portfolio'}>
                <Button variant="glass" size="lg" className="w-full sm:w-auto" rightIcon={<ArrowRight className="w-4 h-4" />}>
                  {d.cta_secondary_label}
                </Button>
              </Link>
            )}
          </div>
          {arr<string>(d.trust_badges).length > 0 && (
            <div className="pt-6 border-t border-aub-border/60 flex flex-wrap items-center gap-6 text-xs text-aub-text-secondary">
              {arr<string>(d.trust_badges).map((b, i) => (
                <div key={i} className="flex items-center gap-2">
                  <CheckCircle2 className={`w-4 h-4 ${['text-aub-magenta', 'text-aub-purple', 'text-emerald-400'][i % 3]}`} />
                  <span>{b}</span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.8, delay: 0.2 }} className="lg:col-span-5 relative overflow-visible">
          <HeroScene />
        </motion.div>
      </div>
    </section>
  );
};

const Stats: React.FC<{ d: D }> = ({ d }) => {
  const items = arr<{ value: string; label: string; icon?: string }>(d.items);
  if (!items.length) return null;
  return (
    <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className={`grid grid-cols-2 ${items.length >= 4 ? 'lg:grid-cols-4' : items.length === 3 ? 'lg:grid-cols-3' : ''} gap-4 sm:gap-6`}>
        {items.map((it, i) => {
          const Icon = statIcons[it.icon || ''] || Award;
          return (
            <GlassCard key={i} className="p-6 sm:p-8 text-center flex flex-col items-center justify-center">
              <div className={`w-10 h-10 rounded-xl border flex items-center justify-center mb-3 ${statTones[i % 4].box}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="text-3xl sm:text-4xl md:text-5xl font-black text-white font-display text-gradient">{it.value}</div>
              <p className="text-xs sm:text-sm font-semibold uppercase tracking-wider text-aub-text-secondary mt-1">{it.label}</p>
            </GlassCard>
          );
        })}
      </div>
    </section>
  );
};

const ServicesSection: React.FC<{ d: D }> = ({ d }) => {
  const { openQuoteModal } = useModal();
  const servicesData = useServices();
  return (
    <section className={SECTION}>
      <Scroll3DSection intensity="medium">
        <Heading d={d} />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {servicesData.map((service) => {
            const isFeatured = service.isPrimary;
            return (
              <div key={service.id} className={isFeatured ? 'md:col-span-2 lg:col-span-2' : ''}>
                <GlassCard className={`h-full flex flex-col justify-between p-7 sm:p-9 hover:border-aub-magenta/70 ${isFeatured ? 'bg-gradient-to-br from-[#191430] to-[#120D24] border-aub-purple/50 shadow-glow-purple/30' : ''}`}>
                  <div>
                    <div className="flex items-center justify-between mb-6">
                      <div className="w-14 h-14 rounded-2xl bg-aub-card border border-aub-border flex items-center justify-center shadow-lg">
                        {serviceIconMap[service.iconName] || <Sparkles className="w-7 h-7 text-aub-magenta" />}
                      </div>
                      {isFeatured && (
                        <span className="px-3 py-1 rounded-full bg-aub-magenta/20 border border-aub-magenta/40 text-aub-magenta text-xs font-bold uppercase tracking-wider shadow-glow-magenta/20">
                          Primary Discipline
                        </span>
                      )}
                    </div>
                    <h3 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">{service.title}</h3>
                    <p className="text-sm text-aub-text-secondary leading-relaxed mb-6">{isFeatured ? service.fullDescription : service.shortDescription}</p>
                    {service.deliverables.length > 0 && (
                      <div className="space-y-2 mb-6">
                        <p className="text-xs font-semibold text-aub-accent-labels uppercase tracking-wider">Core Deliverables:</p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {service.deliverables.slice(0, 4).map((item, dIdx) => (
                            <div key={dIdx} className="flex items-center gap-2 text-xs text-aub-text-secondary">
                              <span className="w-1.5 h-1.5 rounded-full bg-aub-magenta shrink-0" />
                              <span>{item}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="pt-6 border-t border-aub-border/60 flex items-center justify-between">
                    <button onClick={() => openQuoteModal(service.title)} className="text-xs font-semibold text-aub-accent-labels hover:text-white transition-colors inline-flex items-center gap-1.5">
                      <span>Inquire About This Service</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                    <Link to={`/services/${service.slug || service.id}`} className="text-xs text-aub-text-secondary hover:underline">
                      Learn More →
                    </Link>
                  </div>
                </GlassCard>
              </div>
            );
          })}
        </div>
      </Scroll3DSection>
    </section>
  );
};

const AboutPreview: React.FC<{ d: D }> = ({ d }) => {
  const team = useTeam();
  const founders = team.filter((m) => m.isFounder).slice(0, 2);
  const people = founders.length
    ? founders.map((m) => ({ name: m.name, role: m.role, bio: m.bio }))
    : [
        { name: 'Muhammad Bilal', role: 'Founder & Lead Designer', bio: 'Specializes in brand architecture, typography systems & identity standards.' },
        { name: 'Mohammad Shahwaiz', role: 'Co-Founder & Full-Stack Developer', bio: 'Specializes in interactive 3D WebGL web engineering & responsive architectures.' },
      ];
  return (
    <section className={SECTION}>
      <Scroll3DSection intensity="medium">
        <div className="rounded-3xl glass-panel border border-aub-border/90 p-8 sm:p-12 lg:p-16 relative overflow-hidden shadow-2xl">
          <div className="absolute top-0 right-0 w-96 h-96 bg-aub-magenta/15 rounded-full blur-3xl pointer-events-none" />
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold text-aub-accent-labels uppercase tracking-wider">
                <Users className="w-3.5 h-3.5 text-aub-magenta" />
                <span>{d.eyebrow}</span>
              </div>
              <h2 className="text-3xl sm:text-4xl md:text-5xl font-bold text-white font-display leading-tight">
                {d.title_start} <span className="text-gradient">{d.title_highlight}</span>
              </h2>
              {d.paragraph_1 && <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">{d.paragraph_1}</p>}
              {d.paragraph_2 && <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">{d.paragraph_2}</p>}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                {people.map((p) => (
                  <div key={p.name} className="p-4 rounded-2xl bg-aub-card/80 border border-aub-border shadow-md">
                    <h4 className="font-bold text-white text-sm font-display">{p.name}</h4>
                    <p className="text-xs text-aub-accent-labels">{p.role}</p>
                    {p.bio && <p className="text-xs text-aub-text-secondary mt-1 line-clamp-3">{p.bio}</p>}
                  </div>
                ))}
              </div>
              {d.cta_label && (
                <div className="pt-2">
                  <Link to={d.cta_url || '/about'}>
                    <Button variant="gradient" size="md" rightIcon={<ArrowRight className="w-4 h-4" />}>
                      {d.cta_label}
                    </Button>
                  </Link>
                </div>
              )}
            </div>
            <div className="lg:col-span-5 relative space-y-4">
              <BrandCube />
            </div>
          </div>
        </div>
      </Scroll3DSection>
    </section>
  );
};

const WhyUs: React.FC<{ d: D }> = ({ d }) => (
  <section className={SECTION}>
    <Scroll3DSection intensity="subtle">
      <Heading d={d} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {arr<{ title: string; description: string; icon?: string }>(d.items).map((it, i) => {
          const Icon = statIcons[it.icon || ''] || Users;
          return (
            <GlassCard key={i} className="p-6">
              <div className={`w-12 h-12 rounded-xl border flex items-center justify-center mb-4 ${whyTones[i % 4]}`}>
                <Icon className="w-6 h-6" />
              </div>
              <h4 className="text-lg font-bold text-white font-display mb-2">{it.title}</h4>
              <p className="text-xs sm:text-sm text-aub-text-secondary leading-relaxed">{it.description}</p>
            </GlassCard>
          );
        })}
      </div>
    </Scroll3DSection>
  </section>
);

const Process: React.FC<{ d: D }> = ({ d }) => (
  <section className={SECTION}>
    <Scroll3DSection intensity="medium">
      <Heading d={d} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 relative">
        {arr<{ number: string; title: string; description: string }>(d.steps).map((st, i) => (
          <GlassCard key={i} className="p-6 text-center space-y-3">
            <ProcessOrb {...orbs[i % 4]} />
            <div className="text-3xl font-black text-gradient font-display">{st.number || String(i + 1).padStart(2, '0')}</div>
            <h4 className="text-lg font-bold text-white font-display">{st.title}</h4>
            <p className="text-xs sm:text-sm text-aub-text-secondary leading-relaxed">{st.description}</p>
          </GlassCard>
        ))}
      </div>
    </Scroll3DSection>
  </section>
);

const Portfolio: React.FC<{ d: D }> = ({ d }) => (
  <section className={SECTION}>
    <Scroll3DSection intensity="subtle">
      <Heading d={d} />
      <FeaturedPortfolioSlider />
    </Scroll3DSection>
  </section>
);

const CaseStudies: React.FC<{ d: D }> = ({ d }) => (
  <section className={SECTION}>
    <Scroll3DSection intensity="medium">
      <Heading d={d} />
      <FeaturedCaseStudiesSlider />
    </Scroll3DSection>
  </section>
);

const Blog: React.FC<{ d: D }> = ({ d }) => (
  <section className={SECTION}>
    <Scroll3DSection intensity="subtle">
      <BlogSlider heading={d} />
    </Scroll3DSection>
  </section>
);

const Testimonials: React.FC<{ d: D }> = ({ d }) => (
  <section className={SECTION}>
    <Scroll3DSection intensity="medium">
      <Heading d={d} />
      <TestimonialsSlider />
    </Scroll3DSection>
  </section>
);

const Faq: React.FC<{ d: D }> = ({ d }) => {
  const faqs = useFaqs();
  const home = faqs.filter((f) => f.showOnHome !== false);
  if (!home.length) return null;
  return (
    <section className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
      <Scroll3DSection intensity="subtle">
        <Heading d={d} />
        <Accordion items={home} />
      </Scroll3DSection>
    </section>
  );
};

const FinalCta: React.FC<{ d: D }> = ({ d }) => {
  const { openQuoteModal } = useModal();
  const site = useSite();
  const secondary = d.secondary_url || whatsappLink(site);
  return (
    <section className={SECTION}>
      <Scroll3DSection intensity="dramatic">
        <div className="relative rounded-3xl bg-gradient-to-r from-[#EC008C] via-[#9333EA] to-[#7B2FFF] p-8 sm:p-14 lg:p-20 text-center shadow-2xl overflow-hidden">
          <div className="absolute -top-24 -left-24 w-72 h-72 rounded-full bg-white/15 blur-2xl pointer-events-none" />
          <div className="absolute -bottom-24 -right-24 w-72 h-72 rounded-full bg-black/25 blur-2xl pointer-events-none" />
          <div className="relative z-10 max-w-3xl mx-auto space-y-6">
            {d.badge && (
              <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-black/30 backdrop-blur-md text-white text-xs font-bold uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5" />
                <span>{d.badge}</span>
              </span>
            )}
            <h2 className="text-3xl sm:text-5xl md:text-6xl font-black text-white font-display tracking-tight leading-tight">{d.title}</h2>
            <p className="text-white/90 text-sm sm:text-lg leading-relaxed max-w-2xl mx-auto">{d.description}</p>
            <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => openQuoteModal()}
                className="w-full sm:w-auto px-8 py-4 rounded-full bg-white text-black font-extrabold text-sm sm:text-base shadow-xl hover:bg-neutral-100 transition-transform hover:scale-105 active:scale-95 flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4 text-aub-magenta" />
                <span>{d.primary_label || 'Get a Free Quote'}</span>
              </button>
              {d.secondary_label && secondary && (
                <a
                  href={secondary}
                  target={secondary.startsWith('/') ? undefined : '_blank'}
                  rel="noopener noreferrer"
                  className="w-full sm:w-auto px-8 py-4 rounded-full bg-black/40 hover:bg-black/60 backdrop-blur-md border border-white/20 text-white font-bold text-sm sm:text-base transition-transform hover:scale-105 active:scale-95 flex items-center justify-center gap-2"
                >
                  <Phone className="w-4 h-4 text-[#25D366]" />
                  <span>{d.secondary_label}</span>
                </a>
              )}
            </div>
            {d.footnote && <p className="text-xs text-white/70 pt-2">{d.footnote}</p>}
          </div>
        </div>
      </Scroll3DSection>
    </section>
  );
};

const RENDERERS: Record<string, React.FC<{ d: D }>> = {
  hero: Hero,
  stats: Stats,
  services: ServicesSection,
  about_preview: AboutPreview,
  why_us: WhyUs,
  process: Process,
  portfolio: Portfolio,
  case_studies: CaseStudies,
  blog: Blog,
  testimonials: Testimonials,
  faq: Faq,
  final_cta: FinalCta,
};

export const HomePage: React.FC = () => {
  const sections = useHomeSections();
  return (
    <div className="relative pt-24 sm:pt-28 pb-16">
      {sections.map((s) => {
        const R = RENDERERS[s.key];
        return R ? <R key={s.key} d={s.data} /> : null;
      })}
    </div>
  );
};
