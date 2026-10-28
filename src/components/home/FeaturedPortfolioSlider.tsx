import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { useProjects } from '../../context/CmsContext';
import { RevealImage } from '../ui/RevealImage';
import { GlassCard } from '../ui/GlassCard';
import { SnapCarousel } from '../ui/SnapCarousel';

export const FeaturedPortfolioSlider: React.FC = () => {
  const projectsData = useProjects();
  if (!projectsData.length) return null;
  return (
    <div className="relative w-full">
      <SnapCarousel
        label="Featured projects"
        header={
          <p className="text-xs font-mono text-aub-text-secondary">
            <span className="text-aub-accent-labels font-bold">{projectsData.length}</span> selected projects · swipe or use arrows
          </p>
        }
      >
        {projectsData.map((project) => (
          <div key={project.id} className="h-full">
            <Link to={`/portfolio/${project.slug}`} className="block group h-full">
              <GlassCard className="h-full flex flex-col p-4 sm:p-5 hover:border-aub-magenta/50">
                {/* Thumbnail with zoom effect */}
                <div className="relative w-full h-56 sm:h-64 rounded-xl overflow-hidden bg-aub-card/80 mb-5">
                  <RevealImage src={project.thumbnail} alt={project.title} />
                  <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12] via-transparent to-transparent opacity-80" />

                  {/* Category Pill */}
                  <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-xs font-semibold text-white">
                    {project.category}
                  </div>

                  {/* Year Tag */}
                  <div className="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-aub-card/70 backdrop-blur-md text-[11px] font-mono text-aub-text-secondary border border-aub-border">
                    {project.year}
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xl font-bold text-white group-hover:text-aub-magenta transition-colors font-display">
                        {project.title}
                      </h3>
                      <div className="w-8 h-8 rounded-full bg-aub-card border border-aub-border flex items-center justify-center text-aub-accent-labels group-hover:bg-aub-gradient group-hover:text-white transition-all">
                        <ArrowUpRight className="w-4 h-4" />
                      </div>
                    </div>
                    <p className="text-xs text-aub-accent-labels font-medium mb-2">{project.client}</p>
                    <p className="text-sm text-aub-text-secondary line-clamp-2 leading-relaxed">
                      {project.summary}
                    </p>
                  </div>

                  {/* Deliverables snippet */}
                  <div className="mt-4 pt-4 border-t border-aub-border/60 flex flex-wrap gap-1.5">
                    {project.deliverables.slice(0, 2).map((del, dIdx) => (
                      <span
                        key={dIdx}
                        className="px-2 py-0.5 rounded-md bg-aub-card/50 text-[11px] text-aub-text-secondary border border-aub-border/40"
                      >
                        {del}
                      </span>
                    ))}
                  </div>
                </div>
              </GlassCard>
            </Link>
          </div>
        ))}
      </SnapCarousel>

      {/* CTA Button */}
      <div className="mt-8 text-center">
        <Link
          to="/portfolio"
          className="inline-flex items-center justify-center gap-2 min-h-[48px] px-8 py-3.5 rounded-full glass-panel border border-aub-border hover:border-aub-magenta text-white font-semibold text-sm hover:bg-white/5 transition-all"
        >
          <span>View All Completed Projects</span>
          <ArrowUpRight className="w-4 h-4 text-aub-accent-labels" />
        </Link>
      </div>
    </div>
  );
};
