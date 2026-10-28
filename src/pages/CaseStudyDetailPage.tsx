import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, 
  Sparkles, 
  CheckCircle2, 
  TrendingUp, 
  Quote, 
  ArrowRight,
  ShieldCheck,
  Award
} from 'lucide-react';
import { useCaseStudies, useCms } from '../context/CmsContext';
import { useDetail } from '../lib/useDetail';
import { NotFoundPage } from './NotFoundPage';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { useModal } from '../context/ModalContext';

export const CaseStudyDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { openQuoteModal } = useModal();

  const caseStudiesData = useCaseStudies();
  const { status: cmsStatus } = useCms();
  const state = useDetail('case-studies', slug, caseStudiesData, cmsStatus !== 'loading');
  if (state.status === 'loading') {
    return <div className="pt-40 pb-40 text-center text-aub-text-secondary text-sm" role="status">Loading…</div>;
  }
  if (state.status === 'notfound') {
    return <NotFoundPage />;
  }
  const study = state.item;

  const otherStudies = caseStudiesData.filter(c => c.id !== study.id);

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* 1. TOP BREADCRUMB */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-8">
        <Link
          to="/case-studies"
          className="inline-flex items-center gap-2 text-xs font-semibold text-aub-accent-labels hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to All Case Studies</span>
        </Link>
      </div>

      {/* 2. CASE STUDY HERO */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        <div className="space-y-4 max-w-4xl">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-magenta">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{study.client} · {study.industry}</span>
          </div>

          <h1 className="fluid-h1 font-extrabold text-white font-display">
            {study.title}
          </h1>

          <p className="text-base sm:text-lg text-aub-text-secondary leading-relaxed">
            {study.summary}
          </p>
        </div>

        {/* Verified Results Bar */}
        <div className="mt-8 p-6 rounded-2xl glass-panel border border-aub-border/80 grid grid-cols-1 sm:grid-cols-3 gap-6">
          {study.results.map((res, idx) => (
            <div key={idx} className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-aub-magenta/20 border border-aub-magenta/40 flex items-center justify-center text-aub-magenta shrink-0">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <div className="text-2xl sm:text-3xl font-black text-white font-display text-gradient">
                  {res.value}
                </div>
                <div className="text-xs text-aub-text-primary font-semibold">{res.label}</div>
                <div className="text-[11px] text-aub-text-secondary">{res.change}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Hero Cover Image */}
        <div className="mt-8 rounded-3xl overflow-hidden border border-aub-border/90 shadow-2xl relative h-[360px] sm:h-[500px]">
          <img
            src={study.heroImage}
            alt={study.title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12]/80 via-transparent to-transparent" />
        </div>
      </section>

      {/* 3. CASE STUDY STORY */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
          {/* Main Story (8 cols) */}
          <div className="lg:col-span-8 space-y-12">
            {/* The Challenge */}
            <div className="space-y-4">
              <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
                The Core Challenge
              </h2>
              <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">
                {study.challenge}
              </p>
            </div>

            {/* Strategic Approach */}
            <div className="space-y-4">
              <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
                Creative Strategy & Architecture
              </h2>
              <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">
                {study.strategy}
              </p>
            </div>

            {/* Final Solution */}
            <div className="space-y-4">
              <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
                The Final Solution
              </h2>
              <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">
                {study.solution}
              </p>
            </div>

            {/* Client Testimonial */}
            {study.testimonial && (
              <GlassCard className="p-8 sm:p-10 border-aub-magenta/40 relative">
                <Quote className="w-10 h-10 text-aub-magenta/40 mb-4" />
                <blockquote className="text-lg sm:text-xl font-medium text-white italic leading-relaxed font-display">
                  "{study.testimonial.quote}"
                </blockquote>
                <div className="mt-6 pt-6 border-t border-aub-border/60 flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-white font-display">{study.testimonial.author}</h4>
                    <p className="text-xs text-aub-accent-labels">{study.testimonial.role} · {study.testimonial.country}</p>
                  </div>
                  <div className="flex items-center gap-1 text-amber-400 text-xs font-bold">
                    ★★★★★
                  </div>
                </div>
              </GlassCard>
            )}

            {/* Gallery Mockups */}
            <div className="space-y-6 pt-4">
              <h3 className="text-xl font-bold text-white font-display">Project Gallery</h3>
              <div className="grid grid-cols-1 gap-6">
                {study.galleryImages.map((img, idx) => (
                  <div key={idx} className="rounded-2xl overflow-hidden border border-aub-border/80 h-[300px] sm:h-[420px]">
                    <img src={img} alt={`${study.title} visual ${idx + 1}`} className="w-full h-full object-cover" loading="lazy" />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar Deliverables & CTA (4 cols) */}
          <div className="lg:col-span-4 space-y-6">
            <GlassCard className="p-6 sm:p-8 space-y-6 border-aub-purple/40 sticky top-28">
              <div>
                <span className="text-xs font-bold text-aub-magenta uppercase tracking-wider">
                  Deliverables Summary
                </span>
                <h3 className="text-xl font-bold text-white font-display mt-1">What We Built</h3>
              </div>

              <ul className="space-y-3">
                {study.deliverables.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2.5 text-xs sm:text-sm text-aub-text-primary">
                    <CheckCircle2 className="w-4 h-4 text-aub-magenta shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>

              <div className="pt-4 border-t border-aub-border/60">
                <Button
                  variant="gradient"
                  size="md"
                  className="w-full"
                  onClick={() => openQuoteModal(study.category)}
                >
                  Start Similar Project
                </Button>
              </div>

              <div className="text-center pt-2">
                <a
                  href="https://wa.me/923272755118"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-semibold text-[#25D366] hover:underline"
                >
                  Chat on WhatsApp about this case study →
                </a>
              </div>
            </GlassCard>
          </div>
        </div>
      </section>

      {/* 4. OTHER CASE STUDIES */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 border-t border-aub-border/60">
        <h2 className="text-2xl font-bold text-white font-display mb-8">More Case Studies</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {otherStudies.map(other => (
            <Link key={other.id} to={`/case-studies/${other.slug}`} className="block group">
              <GlassCard className="p-5 flex flex-col sm:flex-row gap-5 items-center hover:border-aub-magenta/50">
                <div className="w-full sm:w-48 h-36 rounded-xl overflow-hidden bg-aub-card shrink-0">
                  <img src={other.heroImage} alt={other.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                </div>
                <div className="space-y-2 flex-1">
                  <span className="text-xs text-aub-magenta font-semibold">{other.client}</span>
                  <h3 className="text-lg font-bold text-white group-hover:text-aub-magenta transition-colors font-display">
                    {other.title}
                  </h3>
                  <p className="text-xs text-aub-text-secondary line-clamp-2 leading-relaxed">
                    {other.summary}
                  </p>
                </div>
              </GlassCard>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
};
