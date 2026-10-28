import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, TrendingUp, ArrowRight, CheckCircle2 } from 'lucide-react';
import { StickyStack, StickyCard } from '../components/ui/StickyCard';
import { HorizontalScrollTabs } from '../components/ui/HorizontalScrollTabs';
import { useCaseStudies } from '../context/CmsContext';
import { useModal } from '../context/ModalContext';

export const CaseStudiesPage: React.FC = () => {
  const [selectedIndustry, setSelectedIndustry] = useState('All');
  const { openQuoteModal } = useModal();
  const caseStudiesData = useCaseStudies();

  const industries = ['All', ...Array.from(new Set(caseStudiesData.map(c => c.industry).filter(Boolean)))];

  const filtered = selectedIndustry === 'All'
    ? caseStudiesData
    : caseStudiesData.filter(c => c.industry === selectedIndustry);

  return (
    <div className="relative pt-20 sm:pt-24 pb-28">
      {/* 1. HERO */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-10 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-5 shadow-md">
          <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
          <span>Interactive Stacked Case Studies</span>
        </div>

        <h1 className="fluid-h1 font-extrabold text-white font-display max-w-4xl mx-auto">
          Selected Work. <span className="text-gradient">Measurable Impact.</span>
        </h1>

        <p className="mt-4 sm:mt-5 text-sm sm:text-base text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          Scroll down to experience our stacked case study archive. Each engagement represents verified growth, institutional capital closed, and audience transformation.
        </p>

        {/* Industry Filter Tabs (Horizontally scrollable on mobile and desktop) */}
        <div className="mt-8 max-w-4xl mx-auto">
          <HorizontalScrollTabs
            tabs={industries}
            activeTab={selectedIndustry}
            onTabChange={setSelectedIndustry}
            centerOnDesktop={true}
          />
        </div>
      </section>

      {/* 2. STICKY STACKED CASE STUDY CARDS (NO CUT-OFF) */}
      <section className="relative max-w-5xl mx-auto px-3 sm:px-6 lg:px-8 py-4">
        <StickyStack key={selectedIndustry}>
          {filtered.map((study, index) => (
            <StickyCard
              key={study.id}
              index={index}
              totalCards={filtered.length}
              className="rounded-2xl sm:rounded-3xl bg-gradient-to-br from-[#191430] via-[#120D24] to-[#0B0B12] border border-aub-border/90 p-4 sm:p-6 lg:p-7 shadow-2xl shadow-black/95 backdrop-blur-2xl relative group"
            >
              {/* Card Ambient Lighting Glows */}
              <div className="absolute top-0 right-0 w-80 h-80 bg-aub-magenta/15 rounded-full blur-3xl pointer-events-none" />
              <div className="absolute bottom-0 left-0 w-80 h-80 bg-aub-purple/20 rounded-full blur-3xl pointer-events-none" />

              {/* Top Card Header */}
              <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-aub-border/60 mb-4 sm:mb-5 relative z-10">
                <div className="flex items-center gap-2.5 sm:gap-3">
                  <span className="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-aub-card border border-aub-border flex items-center justify-center text-xs font-mono font-bold text-aub-magenta shrink-0">
                    0{index + 1}
                  </span>
                  <div>
                    <span className="text-xs sm:text-sm font-bold text-aub-accent-labels uppercase tracking-widest block font-display leading-tight">
                      {study.client}
                    </span>
                    <span className="text-[10px] text-aub-text-secondary">{study.industry}</span>
                  </div>
                </div>

                <div className="px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-[10px] sm:text-xs font-semibold text-white">
                  {study.category}
                </div>
              </div>

              {/* Main 2-Column Showcase */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-7 items-center relative z-10">
                {/* Visual Preview (7 cols) */}
                <div className="lg:col-span-7 space-y-3">
                  <div className="relative w-full h-[180px] sm:h-[220px] lg:h-[250px] rounded-2xl overflow-hidden border border-aub-border/90 bg-aub-card shadow-xl group-hover:border-aub-magenta/50 transition-colors">
                    <img
                      src={study.heroImage}
                      alt={study.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12]/95 via-[#0B0B12]/30 to-transparent" />

                    {/* Verified Metrics Overlay at Bottom of Image */}
                    <div className="absolute bottom-2.5 left-2.5 right-2.5 sm:bottom-3 sm:left-3 sm:right-3 grid grid-cols-3 gap-1.5 sm:gap-2">
                      {study.results.map((res, rIdx) => (
                        <div key={rIdx} className="p-1.5 sm:p-2 rounded-xl bg-black/80 backdrop-blur-md border border-white/10 text-center">
                          <div className="text-xs sm:text-base font-black text-white font-display text-gradient">
                            {res.value}
                          </div>
                          <div className="text-[9px] sm:text-[10px] text-aub-text-secondary truncate mt-0.5">
                            {res.label}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right Column: Case Story & Action (5 cols) */}
                <div className="lg:col-span-5 space-y-3 sm:space-y-4">
                  <div>
                    <h2 className="text-base sm:text-xl lg:text-2xl font-bold text-white font-display leading-tight mb-2">
                      {study.title}
                    </h2>
                    <p className="text-xs text-aub-text-secondary leading-relaxed line-clamp-3">
                      {study.summary}
                    </p>
                  </div>

                  {/* Deliverables snippet */}
                  <div className="space-y-1.5">
                    <p className="text-[10px] sm:text-[11px] font-semibold text-aub-accent-labels uppercase tracking-wider">
                      Included Deliverables:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {study.deliverables.slice(0, 3).map((d, dIdx) => (
                        <span
                          key={dIdx}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-aub-card/80 text-[10px] text-white border border-aub-border"
                        >
                          <CheckCircle2 className="w-3 h-3 text-aub-magenta" />
                          <span>{d}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Primary CTA Button */}
                  <div className="pt-1 flex items-center gap-3">
                    <Link
                      to={`/case-studies/${study.slug}`}
                      className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-aub-gradient text-white text-xs sm:text-sm font-semibold shadow-glow-magenta hover:shadow-glow-purple transition-all duration-300 hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <span>Read Case Study Story</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              </div>
            </StickyCard>
          ))}
        </StickyStack>
      </section>

      {/* 3. BOTTOM CTA */}
      <section className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 text-center">
        <div className="p-8 sm:p-10 rounded-3xl glass-panel border border-aub-purple/50 shadow-2xl">
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">
            Want Similar Results for Your Brand?
          </h2>
          <p className="text-xs sm:text-sm text-aub-text-secondary max-w-lg mx-auto mb-6 leading-relaxed">
            Let's evaluate your existing positioning and craft a high-conversion digital presence that elevates your valuation.
          </p>
          <button
            onClick={() => openQuoteModal()}
            className="px-6 py-3 rounded-full bg-aub-gradient text-white text-xs sm:text-sm font-bold shadow-glow-magenta hover:shadow-glow-purple transition-all hover:scale-105 active:scale-95"
          >
            Schedule Free Growth Strategy Session
          </button>
        </div>
      </section>
    </div>
  );
};
