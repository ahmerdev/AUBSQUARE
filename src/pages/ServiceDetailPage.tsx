import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, CheckCircle2, Sparkles } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { Accordion } from '../components/ui/Accordion';
import { useModal } from '../context/ModalContext';
import { useCms, useServices, useProjects, useCaseStudies } from '../context/CmsContext';
import { useDetail } from '../lib/useDetail';
import { NotFoundPage } from './NotFoundPage';

export const ServiceDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { openQuoteModal } = useModal();
  const services = useServices();
  const projects = useProjects();
  const studies = useCaseStudies();
  const { status } = useCms();
  const state = useDetail('services', slug, services, status !== 'loading');

  if (state.status === 'loading') return <div className="pt-40 pb-40 text-center text-aub-text-secondary text-sm" role="status">Loading…</div>;
  if (state.status === 'notfound') return <NotFoundPage />;
  const s = state.item;

  const relProjects = projects.filter((p) => (s.relatedProjects || []).includes(p.slug)).slice(0, 3);
  const relStudies = studies.filter((c) => (s.relatedCaseStudies || []).includes(c.slug)).slice(0, 3);
  const cta = s.ctaLabel || `Start a ${s.title} project`;
  const faqs = (s.faqs || []).map((f, i) => ({ id: String(i), question: f.question, answer: f.answer }));

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-8">
        <Link to="/services" className="inline-flex items-center gap-2 text-xs font-semibold text-aub-accent-labels hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <span>All services</span>
        </Link>
      </div>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
        <div className="lg:col-span-7 space-y-5">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-magenta">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{(s as any).category || 'Service'}</span>
          </div>
          <h1 className="fluid-h1 font-extrabold text-white font-display">{s.title}</h1>
          <p className="text-base sm:text-lg text-aub-text-secondary leading-relaxed whitespace-pre-line">{s.fullDescription || s.shortDescription}</p>
          <div className="flex flex-wrap items-center gap-4 pt-2">
            {s.ctaUrl ? (
              <a href={s.ctaUrl}><Button variant="gradient" size="lg" rightIcon={<ArrowRight className="w-4 h-4" />}>{cta}</Button></a>
            ) : (
              <Button variant="gradient" size="lg" onClick={() => openQuoteModal(s.title)} rightIcon={<ArrowRight className="w-4 h-4" />}>{cta}</Button>
            )}
            {s.priceLabel && <span className="text-sm font-semibold text-aub-accent-labels">{s.priceLabel}</span>}
          </div>
        </div>
        {s.coverImage && (
          <div className="lg:col-span-5 rounded-3xl overflow-hidden border border-aub-border/90 shadow-2xl aspect-[4/3]">
            <img src={s.coverImage} alt={s.coverAlt || s.title} className="w-full h-full object-cover" />
          </div>
        )}
      </section>

      {(s.benefits.length > 0 || s.deliverables.length > 0) && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 md:grid-cols-2 gap-6">
          {s.benefits.length > 0 && (
            <GlassCard className="p-6 sm:p-8 space-y-4">
              <h2 className="text-xl font-bold text-white font-display">Why it matters</h2>
              <ul className="space-y-2.5">
                {s.benefits.map((b, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white"><CheckCircle2 className="w-4 h-4 text-aub-magenta shrink-0 mt-0.5" /><span>{b}</span></li>
                ))}
              </ul>
            </GlassCard>
          )}
          {s.deliverables.length > 0 && (
            <GlassCard className="p-6 sm:p-8 space-y-4">
              <h2 className="text-xl font-bold text-white font-display">What you receive</h2>
              <ul className="space-y-2.5">
                {s.deliverables.map((d, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-white"><span className="w-1.5 h-1.5 rounded-full bg-aub-magenta shrink-0 mt-2" /><span>{d}</span></li>
                ))}
              </ul>
            </GlassCard>
          )}
        </section>
      )}

      {s.process.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <h2 className="text-2xl font-bold text-white font-display mb-6">How we work</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {s.process.map((p, i) => (
              <GlassCard key={i} className="p-5">
                <span className="text-xs font-mono font-bold text-aub-magenta">{p.step || String(i + 1).padStart(2, '0')}</span>
                <h3 className="text-base font-bold text-white font-display mt-1">{p.title}</h3>
                <p className="text-xs text-aub-text-secondary mt-1 leading-relaxed">{p.description}</p>
              </GlassCard>
            ))}
          </div>
        </section>
      )}

      {(s.gallery || []).length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(s.gallery || []).map((g, i) => (
            <img key={i} src={g} alt={`${s.title} example ${i + 1}`} loading="lazy" className="w-full h-56 object-cover rounded-2xl border border-aub-border/80" />
          ))}
        </section>
      )}

      {(relProjects.length > 0 || relStudies.length > 0) && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <h2 className="text-2xl font-bold text-white font-display mb-6">Related work</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {relProjects.map((p) => (
              <Link key={p.id} to={`/portfolio/${p.slug}`} className="block group">
                <GlassCard className="p-4 hover:border-aub-magenta/50 h-full">
                  {p.thumbnail && <img src={p.thumbnail} alt={p.thumbnailAlt || p.title} loading="lazy" className="w-full h-36 object-cover rounded-xl mb-3" />}
                  <span className="text-xs text-aub-magenta font-semibold">{p.category}</span>
                  <h3 className="text-base font-bold text-white font-display group-hover:text-aub-magenta transition-colors">{p.title}</h3>
                </GlassCard>
              </Link>
            ))}
            {relStudies.map((c) => (
              <Link key={c.id} to={`/case-studies/${c.slug}`} className="block group">
                <GlassCard className="p-4 hover:border-aub-magenta/50 h-full">
                  {c.heroImage && <img src={c.heroImage} alt={c.title} loading="lazy" className="w-full h-36 object-cover rounded-xl mb-3" />}
                  <span className="text-xs text-aub-magenta font-semibold">Case study</span>
                  <h3 className="text-base font-bold text-white font-display group-hover:text-aub-magenta transition-colors">{c.title}</h3>
                </GlassCard>
              </Link>
            ))}
          </div>
        </section>
      )}

      {faqs.length > 0 && (
        <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <h2 className="text-2xl font-bold text-white font-display mb-6">Questions about {s.title}</h2>
          <Accordion items={faqs} />
        </section>
      )}
    </div>
  );
};
