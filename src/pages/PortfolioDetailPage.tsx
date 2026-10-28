import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  ArrowLeft, 
  Sparkles, 
  CheckCircle2, 
  TrendingUp, 
  ArrowRight, 
  Calendar, 
  Briefcase,
  Layers
} from 'lucide-react';
import { useProjects, useCms } from '../context/CmsContext';
import { useDetail } from '../lib/useDetail';
import { NotFoundPage } from './NotFoundPage';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';
import { useModal } from '../context/ModalContext';

export const PortfolioDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const { openQuoteModal } = useModal();

  const projectsData = useProjects();
  const { status: cmsStatus } = useCms();
  const state = useDetail('projects', slug, projectsData, cmsStatus !== 'loading');
  if (state.status === 'loading') {
    return <div className="pt-40 pb-40 text-center text-aub-text-secondary text-sm" role="status">Loading…</div>;
  }
  if (state.status === 'notfound') {
    return <NotFoundPage />;
  }
  const project = state.item;

  const relatedProjects = projectsData
    .filter(p => p.id !== project.id)
    .slice(0, 2);

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* 1. TOP BREADCRUMB & BACK LINK */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-8">
        <Link
          to="/portfolio"
          className="inline-flex items-center gap-2 text-xs font-semibold text-aub-accent-labels hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Portfolio</span>
        </Link>
      </div>

      {/* 2. PROJECT HERO */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
        <div className="space-y-4 max-w-4xl">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-magenta">
            <span>{project.category}</span>
          </div>

          <h1 className="fluid-h1 font-extrabold text-white font-display">
            {project.title}
          </h1>

          <p className="text-base sm:text-lg text-aub-text-secondary leading-relaxed">
            {project.summary}
          </p>
        </div>

        {/* Project Meta Bar */}
        <div className="mt-8 p-6 rounded-2xl glass-panel border border-aub-border/80 grid grid-cols-2 sm:grid-cols-4 gap-6 text-xs">
          <div>
            <span className="text-aub-text-secondary uppercase tracking-wider block font-semibold mb-1">Client</span>
            <span className="text-white font-bold text-sm">{project.client}</span>
          </div>
          <div>
            <span className="text-aub-text-secondary uppercase tracking-wider block font-semibold mb-1">Timeline / Year</span>
            <span className="text-white font-bold text-sm">{project.year}</span>
          </div>
          <div>
            <span className="text-aub-text-secondary uppercase tracking-wider block font-semibold mb-1">Discipline</span>
            <span className="text-white font-bold text-sm">{project.category}</span>
          </div>
          <div>
            <span className="text-aub-text-secondary uppercase tracking-wider block font-semibold mb-1">Scope</span>
            <span className="text-aub-accent-labels font-bold text-sm">{project.servicesProvided[0] || '—'}</span>
          </div>
        </div>

        {/* Hero Featured Image */}
        <div className="mt-8 rounded-3xl overflow-hidden border border-aub-border/90 shadow-2xl relative h-[360px] sm:h-[520px]">
          <img
            src={project.thumbnail}
            alt={project.thumbnailAlt || project.title}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12]/80 via-transparent to-transparent" />
        </div>
      </section>

      {/* 3. CASE DEEP DIVE: CHALLENGE & SOLUTION */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
          <div className="lg:col-span-8 space-y-10">
            {/* The Challenge */}
            <div className="space-y-4">
              <h2 className="text-2xl font-bold text-white font-display">The Challenge</h2>
              <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">
                {project.challenge}
              </p>
            </div>

            {/* The Solution */}
            <div className="space-y-4">
              <h2 className="text-2xl font-bold text-white font-display">Strategic Solution</h2>
              <p className="text-sm sm:text-base text-aub-text-secondary leading-relaxed">
                {project.solution}
              </p>
            </div>

            {/* Gallery Images */}
            {project.images.length > 0 && (<div className="space-y-6 pt-4">
              <h3 className="text-xl font-bold text-white font-display">Project Gallery & Deliverables</h3>
              <div className="grid grid-cols-1 gap-6">
                {project.images.map((img, idx) => (
                  <div key={idx} className="rounded-2xl overflow-hidden border border-aub-border/80 h-[320px] sm:h-[450px]">
                    <img src={img} alt={`${project.title} visual ${idx + 1}`} className="w-full h-full object-cover" loading="lazy" />
                  </div>
                ))}
              </div>
            </div>)}
          </div>

          {/* Right Column: Deliverables Box, Metrics, Testimonial */}
          <div className="lg:col-span-4 space-y-6">
            {/* Deliverables Card */}
            <GlassCard className="p-6 space-y-4 border-aub-purple/40">
              <h3 className="text-base font-bold text-white font-display">Delivered Assets</h3>
              <ul className="space-y-2.5">
                {project.deliverables.map((del, dIdx) => (
                  <li key={dIdx} className="flex items-start gap-2 text-xs text-white">
                    <CheckCircle2 className="w-4 h-4 text-aub-magenta shrink-0 mt-0.5" />
                    <span>{del}</span>
                  </li>
                ))}
              </ul>

              <div className="pt-4 border-t border-aub-border/60">
                <Button
                  variant="gradient"
                  size="md"
                  className="w-full"
                  onClick={() => openQuoteModal(project.servicesProvided[0])}
                >
                  Request Similar Project
                </Button>
              </div>
            </GlassCard>

            {/* Metrics */}
            {project.metrics && project.metrics.length > 0 && (
              <GlassCard className="p-6 space-y-4">
                <h3 className="text-base font-bold text-white font-display flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <span>Key Project Impact</span>
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  {project.metrics.map((m, mIdx) => (
                    <div key={mIdx} className="p-3 rounded-xl bg-aub-card border border-aub-border">
                      <div className="text-2xl font-black text-white font-display text-gradient">
                        {m.value}
                      </div>
                      <div className="text-xs text-aub-text-secondary mt-1">
                        {m.label}
                      </div>
                    </div>
                  ))}
                </div>
              </GlassCard>
            )}

            {/* Testimonial */}
            {project.testimonial && (
              <GlassCard className="p-6 space-y-4 border-aub-magenta/30">
                <span className="text-xs font-semibold text-aub-magenta uppercase tracking-wider">
                  Client Feedback
                </span>
                <p className="text-xs sm:text-sm text-white italic leading-relaxed">
                  "{project.testimonial.quote}"
                </p>
                <div className="pt-2 border-t border-aub-border/40 text-xs">
                  <span className="font-bold text-white block">{project.testimonial.author}</span>
                  <span className="text-aub-text-secondary">{project.testimonial.role}</span>
                </div>
              </GlassCard>
            )}
          </div>
        </div>
      </section>

      {/* 4. RELATED PROJECTS */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 border-t border-aub-border/60">
        <h2 className="text-2xl font-bold text-white font-display mb-8">Related Client Engagements</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {relatedProjects.map(rel => (
            <Link key={rel.id} to={`/portfolio/${rel.slug}`} className="block group">
              <GlassCard className="p-5 flex flex-col sm:flex-row gap-5 items-center hover:border-aub-magenta/50">
                <div className="w-full sm:w-48 h-36 rounded-xl overflow-hidden bg-aub-card shrink-0">
                  <img src={rel.thumbnail} alt={rel.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                </div>
                <div className="space-y-2 flex-1">
                  <span className="text-xs text-aub-magenta font-semibold">{rel.category}</span>
                  <h3 className="text-lg font-bold text-white group-hover:text-aub-magenta transition-colors font-display">
                    {rel.title}
                  </h3>
                  <p className="text-xs text-aub-text-secondary line-clamp-2 leading-relaxed">
                    {rel.summary}
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
