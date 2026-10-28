import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Sparkles, 
  ArrowRight, 
  Users, 
  Target, 
  ShieldCheck, 
  Zap, 
  Globe2, 
  Award,
  Layers,
  HeartHandshake,
  CheckCircle2
} from 'lucide-react';
import { SectionHeading } from '../components/ui/SectionHeading';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { TestimonialsSlider } from '../components/home/TestimonialsSlider';
import { useModal } from '../context/ModalContext';
import { useCms, useTeam } from '../context/CmsContext';

const valueIcons = [Target, Zap, HeartHandshake, ShieldCheck, Layers, Award];
const valueTones = ['bg-aub-magenta/20 border-aub-magenta/40 text-aub-magenta', 'bg-aub-purple/20 border-aub-purple/40 text-aub-purple', 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'];
const Gradient: React.FC<{ text: string }> = ({ text }) => {
  const w = text.trim().split(/\s+/);
  if (w.length < 3) return <>{text}</>;
  const n = Math.min(2, Math.floor(w.length / 2));
  return <>{w.slice(0, -n).join(' ')} <span className="text-gradient">{w.slice(-n).join(' ')}</span></>;
};

export const AboutPage: React.FC = () => {
  const { openQuoteModal } = useModal();
  const a = useCms().data?.about as Record<string, any> | undefined;
  const team = useTeam();
  const heroTitle: string = a?.heroTitle || 'We Believe Great Design Is An Unfair Advantage.';
  const stats: { value: string; label: string }[] = a ? a.stats || [] : [{ value: '500+', label: 'Projects' }, { value: '6+ Years', label: 'Experience' }, { value: 'Worldwide', label: 'Reach' }];
  const values: { title: string; description: string }[] = a ? a.values || [] : [
    { title: 'Precision & Craft', description: 'No shortcuts. Every kerning pair, color contrast ratio, and pixel is art-directed for perfection.' },
    { title: 'Commercial Efficacy', description: 'Design must generate revenue, shorten sales cycles, and elevate perceived value.' },
    { title: 'Founder-to-Founder Transparency', description: 'Direct, honest counsel. We treat your marketing budget with the same stewardship as our own.' },
  ];
  const people = team.length ? team : [
    { id: 1, name: 'Muhammad Bilal', role: 'Founder & Lead Designer', bio: 'Leads the creative vision for all AUB SQUARE brand programs.', photo: '', photoAlt: 'Muhammad Bilal', specialties: ['Brand Identity', 'Design Systems'], isFounder: true, linkedin: '', twitter: '' },
    { id: 2, name: 'Mohammad Shahwaiz', role: 'Co-Founder & Full-Stack Developer', bio: 'Architects high-performance web systems with React, TypeScript and interactive 3D WebGL scenes.', photo: '', photoAlt: 'Mohammad Shahwaiz', specialties: ['React & 3D WebGL', 'Full-Stack Architecture'], isFounder: true, linkedin: '', twitter: '' },
  ];

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* 1. HERO */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-16 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-6">
          <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
          <span>{a ? a.heroEyebrow : 'About AUB SQUARE Creative Studio'}</span>
        </div>

        <h1 className="fluid-h1 font-extrabold text-white font-display max-w-4xl mx-auto">
          <Gradient text={heroTitle} />
        </h1>

        <p className="mt-6 text-base sm:text-lg text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          {a ? a.heroDescription : 'Founded on the principle that startups and growing businesses should never look small or unproven. We combine strategic brand positioning with cutting-edge 3D web engineering.'}
        </p>
      </section>

      {/* 2. OUR FOUNDING STORY */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold text-aub-accent-labels uppercase tracking-wider">
              <span>The Journey</span>
            </div>
            {a ? (
              <>
                {a.storyTitle && <h2 className="text-3xl sm:text-4xl font-bold text-white font-display leading-tight"><Gradient text={a.storyTitle} /></h2>}
                <div className="cms-prose" dangerouslySetInnerHTML={{ __html: a.storyHtml || '' }} />
                {(a.mission || a.vision) && (
                  <div className="grid sm:grid-cols-2 gap-4 pt-2">
                    {a.mission && <div className="p-4 rounded-2xl bg-aub-card/80 border border-aub-border"><h4 className="text-sm font-bold text-white font-display">Mission</h4><p className="text-xs text-aub-text-secondary mt-1 leading-relaxed">{a.mission}</p></div>}
                    {a.vision && <div className="p-4 rounded-2xl bg-aub-card/80 border border-aub-border"><h4 className="text-sm font-bold text-white font-display">Vision</h4><p className="text-xs text-aub-text-secondary mt-1 leading-relaxed">{a.vision}</p></div>}
                  </div>
                )}
              </>
            ) : (
              <>
                <h2 className="text-3xl sm:text-4xl font-bold text-white font-display leading-tight">
                  From Passionate Freelancers to an <span className="text-gradient">International Agency</span>
                </h2>
                <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">
                  Muhammad Bilal, a brand identity designer, joined forces with Mohammad Shahwaiz, a full-stack engineer passionate about interactive 3D WebGL experiences, to offer one cohesive creative service: from the vector curve of a logo mark to animated 3D web platforms.
                </p>
              </>
            )}
            {stats.length > 0 && (
              <div className="pt-2 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-aub-accent-labels font-semibold">
                {stats.map((st, i) => (
                  <span key={i} className="flex items-center gap-1.5"><CheckCircle2 className={`w-4 h-4 ${['text-aub-magenta', 'text-aub-purple', 'text-emerald-400'][i % 3]}`} /> {st.value} {st.label}</span>
                ))}
              </div>
            )}
          </div>

          <div className="lg:col-span-6">
            <GlassCard className="p-8 space-y-6 border-aub-purple/40">
              <h3 className="text-xl font-bold text-white font-display">Our Core Agency Values</h3>
              <div className="space-y-4">
                {values.map((v, i) => {
                  const Icon = valueIcons[i % valueIcons.length];
                  return (
                    <div key={i} className="flex gap-4 items-start">
                      <div className={`w-10 h-10 rounded-xl border flex items-center justify-center shrink-0 ${valueTones[i % 3]}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-white font-display">{v.title}</h4>
                        <p className="text-xs text-aub-text-secondary leading-relaxed mt-0.5">{v.description}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          </div>
        </div>
      </section>

      {/* 3. LEADERSHIP TEAM */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <SectionHeading
          eyebrow="Leadership"
          title="The Founders Behind the Craft"
          gradientWord="Founders"
          subtitle="You will collaborate directly with our founding partners throughout your project."
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {people.map((m, i) => (
            <GlassCard key={m.id} className={`p-8 flex flex-col items-center text-center ${i % 2 ? 'hover:border-aub-purple/50' : 'hover:border-aub-magenta/50'}`}>
              <div className={`w-28 h-28 rounded-full overflow-hidden border-2 mb-6 flex items-center justify-center bg-aub-card ${i % 2 ? 'border-aub-purple' : 'border-aub-magenta'}`}>
                {m.photo ? (
                  <img src={m.photo} alt={m.photoAlt || m.name} loading="lazy" className="w-full h-full object-cover" />
                ) : (
                  <span className="text-3xl font-black text-gradient font-display" aria-hidden="true">{m.name.slice(0, 1)}</span>
                )}
              </div>
              <h3 className="text-2xl font-bold text-white font-display">{m.name}</h3>
              <p className="text-sm text-aub-accent-labels font-semibold mt-1">{m.role}</p>
              {m.bio && <p className="text-xs sm:text-sm text-aub-text-secondary mt-4 leading-relaxed">{m.bio}</p>}
              {m.specialties.length > 0 && (
                <div className="mt-6 pt-6 border-t border-aub-border/60 w-full flex flex-wrap items-center justify-center gap-2">
                  <span className="text-xs text-aub-text-secondary">Specialties:</span>
                  {m.specialties.map((sp) => (<span key={sp} className="px-2.5 py-1 rounded-md bg-aub-card text-[11px] text-white border border-aub-border">{sp}</span>))}
                </div>
              )}
            </GlassCard>
          ))}
        </div>
      </section>

      {/* 4. CLIENT TESTIMONIALS PREVIEW */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <SectionHeading
          eyebrow="Reputation"
          title="Trusted By Founders Globally"
          gradientWord="Globally"
          subtitle="What leaders across the USA, UK, Europe, and Asia say about our dedication."
        />
        <TestimonialsSlider />
      </section>

      {/* 5. CTA */}
      <section className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
        <GlassCard className="p-10 sm:p-14 border-aub-purple/50">
          <h2 className="text-3xl sm:text-4xl font-bold text-white font-display mb-4">
            {a?.ctaTitle || 'Ready to Build Your Brand With Us?'}
          </h2>
          <p className="text-sm sm:text-base text-aub-text-secondary max-w-xl mx-auto mb-8">
            {a ? a.ctaText : 'Let’s discuss your upcoming venture or rebrand. We will prepare an exact scope and roadmap.'}
          </p>
          <Button
            variant="gradient"
            size="lg"
            onClick={() => openQuoteModal()}
            rightIcon={<ArrowRight className="w-5 h-5" />}
          >
            {a?.ctaLabel || 'Get a Free Quote'}
          </Button>
        </GlassCard>
      </section>
    </div>
  );
};
