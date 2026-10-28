import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Star, Quote, Sparkles, CheckCircle2 } from 'lucide-react';
import { useTestimonials } from '../../context/CmsContext';
import { GlassCard } from '../ui/GlassCard';
import { SwipeArea } from '../ui/SwipeArea';

export const TestimonialsSlider: React.FC = () => {
  const testimonialsData = useTestimonials();
  const [activeIndex, setActiveIndex] = useState(0);

  const prev = () => {
    setActiveIndex(prev => (prev === 0 ? testimonialsData.length - 1 : prev - 1));
  };

  const next = () => {
    setActiveIndex(prev => (prev === testimonialsData.length - 1 ? 0 : prev + 1));
  };

  const current = testimonialsData[Math.min(activeIndex, testimonialsData.length - 1)];
  if (!current) return null;

  return (
    <div className="relative w-full max-w-5xl mx-auto space-y-8">
      {/* 1. MAIN FEATURED TESTIMONIAL DISPLAY */}
      <SwipeArea label="Client testimonials" onPrev={prev} onNext={next}>
      <div className="relative rounded-3xl bg-gradient-to-br from-[#191430]/95 via-[#120D24]/95 to-[#0B0B12]/95 border border-aub-border/90 p-5 xs:p-6 sm:p-12 lg:p-14 shadow-2xl overflow-hidden">
        {/* Ambient Glows */}
        <div className="absolute top-0 right-0 w-80 h-80 bg-aub-magenta/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-aub-purple/15 rounded-full blur-3xl pointer-events-none" />

        {/* Large Decorative Watermark Quote */}
        <Quote className="absolute -top-6 -right-6 w-36 h-36 text-aub-border/15 pointer-events-none" />

        {/* Top Meta Bar */}
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-aub-border/60">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="w-4 h-4 text-amber-400 fill-amber-400" />
              ))}
            </div>
            <span className="text-xs font-bold text-white font-mono ml-1.5">5.0 / 5.0 Rating</span>
          </div>

          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold text-aub-accent-labels">
            <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
            <span>Project: {current.projectType}</span>
          </div>
        </div>

        {/* Testimonial Quote with Animated Transitions */}
        <div className="relative z-10 my-8 min-h-[140px] sm:min-h-[120px] flex items-center">
          <AnimatePresence mode="wait">
            <motion.blockquote
              key={current.id}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -15 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
              className="text-[1.05rem] xs:text-lg sm:text-2xl md:text-3xl font-medium text-white leading-relaxed font-display"
            >
              "{current.content}"
            </motion.blockquote>
          </AnimatePresence>
        </div>

        {/* Bottom Author Profile & Arrow Controls */}
        <div className="relative z-10 pt-6 border-t border-aub-border/60 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <img
                src={current.avatar}
                alt={current.clientName}
                className="w-14 h-14 rounded-2xl object-cover border-2 border-aub-magenta shadow-glow-magenta/30"
              />
              <span className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full border-2 border-[#120D24] flex items-center justify-center text-[8px] text-black font-black">
                ✓
              </span>
            </div>
            <div>
              <h4 className="text-lg font-bold text-white font-display">
                {current.clientName}
              </h4>
              <p className="text-xs sm:text-sm text-aub-text-secondary">
                {current.role} · <strong className="text-white">{current.company}</strong> ({current.country})
              </p>
            </div>
          </div>

          {/* Navigation Buttons */}
          <div className="flex items-center gap-3">
            <button
              onClick={prev}
              className="w-11 h-11 rounded-full glass-panel flex items-center justify-center text-white hover:border-aub-magenta hover:bg-white/10 transition-all active:scale-95"
              aria-label="Previous testimonial"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="text-xs font-mono font-bold text-aub-text-secondary px-2">
              <span className="text-white">0{activeIndex + 1}</span> / 0{testimonialsData.length}
            </div>
            <button
              onClick={next}
              className="w-11 h-11 rounded-full glass-panel flex items-center justify-center text-white hover:border-aub-magenta hover:bg-white/10 transition-all active:scale-95"
              aria-label="Next testimonial"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
      </SwipeArea>

      {/* 2. INTERACTIVE CLIENT CHIPS SELECTOR (SCROLLABLE ON MOBILE, GRID ON DESKTOP) */}
      <div className="flex sm:grid sm:grid-cols-3 lg:grid-cols-5 gap-2.5 overflow-x-auto no-scrollbar pb-1 touch-pan-x">
        {testimonialsData.map((item, idx) => {
          const isActive = idx === activeIndex;
          return (
            <button
              key={item.id}
              onClick={() => setActiveIndex(idx)}
              className={`shrink-0 sm:shrink min-w-[150px] sm:min-w-0 p-2.5 sm:p-3 rounded-2xl transition-all duration-300 flex items-center gap-2.5 text-left border ${
                isActive
                  ? 'bg-aub-card border-aub-magenta shadow-glow-magenta/30 scale-[1.02]'
                  : 'glass-panel border-aub-border/60 hover:border-aub-purple/50 opacity-70 hover:opacity-100'
              }`}
            >
              <img
                src={item.avatar}
                alt={item.clientName}
                className="w-9 h-9 rounded-xl object-cover shrink-0"
              />
              <div className="overflow-hidden">
                <span className="text-xs font-bold text-white block truncate font-display">
                  {item.clientName}
                </span>
                <span className="text-[10px] text-aub-text-secondary block truncate">
                  {item.company}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
