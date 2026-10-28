import React from 'react';
import { Link } from 'react-router-dom';
import { Clock, Calendar, ArrowRight, BookOpen } from 'lucide-react';
import { useLatestArticles } from '../../context/CmsContext';
import { RevealImage } from '../ui/RevealImage';
import { GlassCard } from '../ui/GlassCard';
import { SnapCarousel } from '../ui/SnapCarousel';

export const BlogSlider: React.FC<{ heading?: Record<string, any> }> = ({ heading }) => {
  const articlesData = useLatestArticles();
  const h = heading || {};
  if (!articlesData.length) return null;
  return (
    <div className="relative w-full">
      <SnapCarousel
        label="Latest articles"
        header={
          <>
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold text-aub-accent-labels uppercase tracking-wider mb-2">
              <BookOpen className="w-3.5 h-3.5 text-aub-magenta" />
              <span>{h.eyebrow || 'Latest Agency Publications'}</span>
            </div>
            <h3 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white font-display leading-tight">
              {h.title || 'Insights, Ideas &'} <span className="text-gradient">{h.gradient_word || (h.title ? '' : 'Creative Inspiration')}</span>
            </h3>
            <p className="text-sm text-aub-text-secondary mt-1 max-w-xl">
              {h.subtitle ?? 'Practical insights, branding advice and creative ideas to help your business grow.'}
            </p>
          </>
        }
      >
        {articlesData.map((article) => (
          <div key={article.id} className="h-full">
            <Link to={`/blog/${article.slug}`} className="block group h-full">
              <GlassCard className="h-full flex flex-col p-5 hover:border-aub-purple/50">
                {/* Article Image */}
                <div className="relative w-full h-48 sm:h-52 rounded-xl overflow-hidden mb-4 bg-aub-card">
                  <RevealImage src={article.featuredImage} alt={article.title} />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12]/80 via-transparent to-transparent" />
                  <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-xs font-semibold text-white">
                    {article.category}
                  </div>
                </div>

                {/* Article Meta */}
                <div className="flex items-center gap-4 text-xs text-aub-text-secondary mb-3">
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-aub-accent-labels" />
                    {article.publishDate}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-aub-magenta" />
                    {article.readingTime}
                  </span>
                </div>

                {/* Title & Excerpt */}
                <div className="flex-1 flex flex-col justify-between">
                  <div>
                    <h4 className="text-lg font-bold text-white group-hover:text-aub-magenta transition-colors line-clamp-2 font-display mb-2">
                      {article.title}
                    </h4>
                    <p className="text-xs sm:text-sm text-aub-text-secondary line-clamp-2 leading-relaxed">
                      {article.excerpt}
                    </p>
                  </div>

                  <div className="mt-4 pt-4 border-t border-aub-border/60 flex items-center justify-between text-xs font-semibold text-aub-accent-labels group-hover:text-white transition-colors">
                    <span>Read Article</span>
                    <ArrowRight className="w-4 h-4 text-aub-magenta group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </GlassCard>
            </Link>
          </div>
        ))}
      </SnapCarousel>

      {/* Bottom CTA */}
      <div className="mt-8 text-center">
        <Link
          to="/blog"
          className="inline-flex items-center justify-center gap-2 min-h-[48px] px-8 py-3.5 rounded-full glass-panel border border-aub-border hover:border-aub-magenta text-white font-semibold text-sm hover:bg-white/5 transition-all"
        >
          <span>View All Articles & Guides</span>
          <ArrowRight className="w-4 h-4 text-aub-accent-labels" />
        </Link>
      </div>
    </div>
  );
};
