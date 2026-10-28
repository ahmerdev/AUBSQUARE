import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Search, ArrowUpRight, Filter, Layers } from 'lucide-react';
import { SectionHeading } from '../components/ui/SectionHeading';
import { RevealImage } from '../components/ui/RevealImage';
import { GlassCard } from '../components/ui/GlassCard';
import { HorizontalScrollTabs } from '../components/ui/HorizontalScrollTabs';
import { useProjects } from '../context/CmsContext';
import { useModal } from '../context/ModalContext';


export const PortfolioPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const { openQuoteModal } = useModal();
  const projectsData = useProjects();
  const categories = ['All', ...Array.from(new Set(projectsData.map(p => p.category).filter(Boolean)))];

  const filteredProjects = projectsData.filter(project => {
    const matchesCategory = selectedCategory === 'All' || project.category === selectedCategory;
    const matchesSearch =
      project.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      project.client.toLowerCase().includes(searchQuery.toLowerCase()) ||
      project.summary.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* 1. HERO */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-12 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-6">
          <Sparkles className="w-3.5 h-3.5 text-aub-magenta" />
          <span>Curated Portfolio</span>
        </div>

        <h1 className="fluid-h1 font-extrabold text-white font-display max-w-4xl mx-auto">
          Visual Identities & Experiences That <span className="text-gradient">Elevate Brands.</span>
        </h1>

        <p className="mt-6 text-base sm:text-lg text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          Explore our completed client engagements spanning national broadcast rebrands, private equity pitch materials, and interactive 3D WebGL platforms.
        </p>

        {/* 2. FILTERS & SEARCH BAR (HORIZONTALLY SCROLLABLE TABS) */}
        <div className="mt-10 max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          {/* Category Tabs */}
          <div className="w-full md:flex-1 min-w-0">
            <HorizontalScrollTabs
              tabs={categories}
              activeTab={selectedCategory}
              onTabChange={setSelectedCategory}
              centerOnDesktop={false}
            />
          </div>

          {/* Search Box */}
          <div className="relative w-full md:w-64 shrink-0">
            <Search className="w-4 h-4 text-aub-text-secondary absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search projects..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              aria-label="Search projects"
              className="w-full pl-9 pr-4 py-2.5 min-h-[44px] rounded-full bg-aub-card/80 backdrop-blur-md border border-aub-border text-base sm:text-xs text-white placeholder-white/30 focus:outline-none focus:border-aub-magenta transition-colors shadow-inner"
            />
          </div>
        </div>
      </section>

      {/* 3. PROJECTS GRID */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {filteredProjects.length === 0 ? (
          <div className="text-center py-20 glass-panel rounded-3xl p-8 max-w-md mx-auto">
            <Layers className="w-12 h-12 text-aub-accent-labels mx-auto mb-4 opacity-50" />
            <h3 className="text-lg font-bold text-white font-display">No Projects Found</h3>
            <p className="text-xs text-aub-text-secondary mt-1">
              Try adjusting your search criteria or resetting filters.
            </p>
            <button
              onClick={() => {
                setSelectedCategory('All');
                setSearchQuery('');
              }}
              className="mt-4 px-4 py-2 rounded-full bg-aub-card border border-aub-border text-xs text-white"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <AnimatePresence>
              {filteredProjects.map((project, idx) => (
                <motion.div
                  key={project.id}
                  layout
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.4, delay: idx * 0.05 }}
                >
                  <Link to={`/portfolio/${project.slug}`} className="block group h-full">
                    <GlassCard className="h-full flex flex-col p-5 hover:border-aub-magenta/50">
                      {/* Image Thumbnail */}
                      <div className="relative w-full h-64 rounded-xl overflow-hidden mb-5 bg-aub-card">
                        <RevealImage src={project.thumbnail} alt={project.title} />
                        <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12] via-transparent to-transparent opacity-80" />

                        {/* Badges */}
                        <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-xs font-semibold text-white">
                          {project.category}
                        </div>
                        <div className="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-aub-card/80 text-[11px] font-mono text-aub-text-secondary border border-aub-border">
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
                            <div className="w-8 h-8 rounded-full bg-aub-card border border-aub-border flex items-center justify-center text-aub-accent-labels group-hover:bg-aub-gradient group-hover:text-white transition-all shrink-0">
                              <ArrowUpRight className="w-4 h-4" />
                            </div>
                          </div>
                          <p className="text-xs text-aub-accent-labels font-semibold mb-2">{project.client}</p>
                          <p className="text-sm text-aub-text-secondary leading-relaxed line-clamp-2">
                            {project.summary}
                          </p>
                        </div>

                        {/* Deliverables tags */}
                        <div className="mt-5 pt-4 border-t border-aub-border/60 flex flex-wrap gap-1.5">
                          {project.deliverables.slice(0, 3).map((d, dIdx) => (
                            <span
                              key={dIdx}
                              className="px-2 py-0.5 rounded-md bg-aub-card/50 text-[11px] text-aub-text-secondary border border-aub-border/40"
                            >
                              {d}
                            </span>
                          ))}
                        </div>
                      </div>
                    </GlassCard>
                  </Link>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </section>

      {/* 4. BOTTOM CTA */}
      <section className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 text-center">
        <GlassCard className="p-10 border-aub-purple/50">
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">
            Have a Project in Mind?
          </h2>
          <p className="text-sm text-aub-text-secondary max-w-md mx-auto mb-6">
            Let’s discuss your brand requirements and create your next signature showcase.
          </p>
          <button
            onClick={() => openQuoteModal()}
            className="px-8 py-3.5 rounded-full bg-aub-gradient text-white font-bold text-sm shadow-glow-magenta hover:shadow-glow-purple transition-all"
          >
            Start Your Project
          </button>
        </GlassCard>
      </section>
    </div>
  );
};
