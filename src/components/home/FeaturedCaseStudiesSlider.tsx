import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, ArrowRight, TrendingUp, CheckCircle, Sparkles } from 'lucide-react';
import { useCaseStudies } from '../../context/CmsContext';
import { SwipeArea } from '../ui/SwipeArea';

export const FeaturedCaseStudiesSlider: React.FC = () => {
  const caseStudiesData = useCaseStudies();
  const [currentIndex, setCurrentIndex] = useState(0);

  const prevSlide = () => {
    setCurrentIndex(prev => (prev === 0 ? caseStudiesData.length - 1 : prev - 1));
  };

  const nextSlide = () => {
    setCurrentIndex(prev => (prev === caseStudiesData.length - 1 ? 0 : prev + 1));
  };

  const currentStudy = caseStudiesData[Math.min(currentIndex, caseStudiesData.length - 1)];
  if (!currentStudy) return null;

  return (
    <div className="relative w-full">
      <SwipeArea label="Featured case studies" onPrev={prevSlide} onNext={nextSlide}>
      {/* Slider Container */}
      <div className="relative rounded-2xl sm:rounded-3xl bg-gradient-to-br from-[#191430]/90 to-[#120D24]/90 border border-aub-border/90 p-4 sm:p-7 lg:p-10 overflow-hidden shadow-2xl">
        {/* Subtle Ambient Glow */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-aub-magenta/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-aub-purple/15 rounded-full blur-3xl pointer-events-none" />

        <AnimatePresence mode="wait">
          <motion.div
            key={currentStudy.id}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -15 }}
            transition={{ duration: 0.45, ease: 'easeOut' }}
            className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-10 items-center"
          >
            {/* Left: Project Image & Highlights (7 cols) */}
            <div className="lg:col-span-7 space-y-3 sm:space-y-4">
              <div className="relative w-full h-[200px] sm:h-[300px] lg:h-[360px] rounded-2xl overflow-hidden border border-aub-border/80 group">
                <img
                  src={currentStudy.heroImage}
                  alt={currentStudy.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12]/90 via-[#0B0B12]/30 to-transparent" />

                {/* Floating Industry Badge */}
                <div className="absolute top-3 left-3 sm:top-4 sm:left-4 px-3 py-1 rounded-full bg-black/70 backdrop-blur-md border border-white/20 text-xs font-semibold text-white">
                  {currentStudy.industry}
                </div>

                {/* Verified Results Grid on Image */}
                <div className="absolute bottom-3 left-3 right-3 sm:bottom-4 sm:left-4 sm:right-4 grid grid-cols-3 gap-1.5 sm:gap-2.5">
                  {currentStudy.results.map((res, rIdx) => (
                    <div
                      key={rIdx}
                      className="p-2 sm:p-2.5 rounded-xl bg-black/70 backdrop-blur-md border border-white/10"
                    >
                      <div className="flex items-center gap-1 text-aub-magenta text-[10px] sm:text-[11px] font-semibold">
                        <TrendingUp className="w-3 h-3" />
                        <span>Verified</span>
                      </div>
                      <div className="text-base sm:text-xl font-black text-white font-display mt-0.5">
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

            {/* Right: Detailed Story & Metrics (5 cols) */}
            <div className="lg:col-span-5 flex flex-col justify-between space-y-6">
              <div>
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold text-aub-accent-labels uppercase tracking-wider mb-3">
                  <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
                  <span>{currentStudy.client}</span>
                </div>

                <h3 className="text-2xl sm:text-3xl font-bold text-white font-display leading-tight mb-4">
                  {currentStudy.title}
                </h3>

                <p className="text-sm text-aub-text-secondary leading-relaxed mb-6">
                  {currentStudy.summary}
                </p>

                {/* Key Deliverables Pills */}
                <div className="space-y-2 mb-6">
                  <p className="text-xs font-semibold text-aub-accent-labels uppercase tracking-wider">
                    Core Solutions Delivered:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {currentStudy.deliverables.slice(0, 3).map((d, dIdx) => (
                      <span
                        key={dIdx}
                        className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-aub-card/80 border border-aub-border/80 text-xs text-white"
                      >
                        <CheckCircle className="w-3 h-3 text-aub-magenta" />
                        <span>{d}</span>
                      </span>
                    ))}
                  </div>
                </div>

                {/* Read Case Study Link */}
                <Link
                  to={`/case-studies/${currentStudy.slug}`}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-aub-gradient text-white text-sm font-semibold shadow-glow-magenta hover:shadow-glow-purple transition-all duration-300 hover:scale-[1.02]"
                >
                  <span>Read Full Case Study</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              </div>

              {/* Slider Controls & Progress */}
              <div className="pt-6 border-t border-aub-border/60 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {caseStudiesData.map((_, dotIdx) => (
                    <button
                      key={dotIdx}
                      onClick={() => setCurrentIndex(dotIdx)}
                      className="h-6 min-w-6 flex items-center justify-center"
                      aria-label={`Go to slide ${dotIdx + 1}`}
                      aria-current={dotIdx === currentIndex}
                    >
                      <span className={`block h-2 rounded-full transition-all duration-300 ${dotIdx === currentIndex ? 'w-8 bg-aub-magenta' : 'w-2 bg-aub-border'}`} />
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={prevSlide}
                    className="w-11 h-11 rounded-full glass-panel flex items-center justify-center text-white hover:border-aub-magenta transition-colors active:scale-95"
                    aria-label="Previous case study"
                  >
                    <ChevronLeft className="w-5 h-5" />
                  </button>
                  <button
                    onClick={nextSlide}
                    className="w-11 h-11 rounded-full glass-panel flex items-center justify-center text-white hover:border-aub-magenta transition-colors active:scale-95"
                    aria-label="Next case study"
                  >
                    <ChevronRight className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
      </SwipeArea>
      <p className="sr-only" aria-live="polite">Showing case study {currentIndex + 1} of {caseStudiesData.length}: {currentStudy.title}</p>

      {/* Explore All Case Studies Link */}
      <div className="mt-8 text-center">
        <Link
          to="/case-studies"
          className="inline-flex items-center gap-2 text-sm font-semibold text-aub-accent-labels hover:text-white transition-colors"
        >
          <span>Explore All Case Studies & Results</span>
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
};
