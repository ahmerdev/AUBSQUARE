import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Calendar, Clock, ArrowRight, BookOpen, Mail, CheckCircle2 } from 'lucide-react';
import { RevealImage } from '../components/ui/RevealImage';
import { GlassCard } from '../components/ui/GlassCard';
import { HorizontalScrollTabs } from '../components/ui/HorizontalScrollTabs';
import { useCms } from '../context/CmsContext';
import { useArticleList } from '../lib/useArticleList';
import { api, ApiError } from '../lib/api';

const Avatar: React.FC<{ src?: string; name: string }> = ({ src, name }) =>
  src ? (
    <img src={src} alt={name} className="w-9 h-9 rounded-full object-cover border border-aub-magenta" />
  ) : (
    <span className="w-9 h-9 rounded-full bg-aub-gradient text-white text-xs font-bold flex items-center justify-center" aria-hidden="true">{name.slice(0, 1)}</span>
  );

export const BlogPage: React.FC = () => {
  const params = useParams<{ categorySlug?: string; tagSlug?: string }>();
  const { data } = useCms();
  const categories = data?.categories ?? [
    { name: 'Branding', slug: 'branding' }, { name: 'Design', slug: 'design' }, { name: 'Web Development', slug: 'web-development' }, { name: 'Marketing', slug: 'marketing' },
  ];
  const [category, setCategory] = useState(params.categorySlug || '');
  const [searchQuery, setSearchQuery] = useState('');
  const tag = params.tagSlug || '';
  useEffect(() => { setCategory(params.categorySlug || ''); }, [params.categorySlug]);

  const { items, count, loading, error, hasMore, loadMore } = useArticleList({ category, tag, q: searchQuery.trim() });
  const selectedName = categories.find((c) => c.slug === category)?.name || 'All';
  const featuredArticle = !category && !tag && !searchQuery ? items.find((a) => a.featured) || items[0] : undefined;
  const filteredArticles = featuredArticle ? items.filter((a) => a.id !== featuredArticle.id) : items;

  const [newsletterEmail, setNewsletterEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [website, setWebsite] = useState(''); // honeypot
  const [nlState, setNlState] = useState<{ status: 'idle' | 'busy' | 'ok' | 'err'; msg: string }>({ status: 'idle', msg: '' });

  const handleNewsletter = async (e: React.FormEvent) => {
    e.preventDefault();
    setNlState({ status: 'busy', msg: '' });
    try {
      const r = await api<{ message?: string }>('/newsletter/subscribe/', { method: 'POST', json: { email: newsletterEmail, consent, website } });
      setNlState({ status: 'ok', msg: r?.message || 'Thanks for subscribing!' });
      setNewsletterEmail('');
    } catch (err) {
      setNlState({ status: 'err', msg: err instanceof ApiError ? err.message : 'Something went wrong. Please try again.' });
    }
  };

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* 1. HERO */}
      <section className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-12 text-center">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-accent-labels mb-6">
          <BookOpen className="w-3.5 h-3.5 text-aub-magenta" />
          <span>Agency Knowledge Base</span>
        </div>

        <h1 className="fluid-h1 font-extrabold text-white font-display max-w-4xl mx-auto">
          Insights, Ideas & <span className="text-gradient">Creative Inspiration.</span>
        </h1>

        <p className="mt-6 text-base sm:text-lg text-aub-text-secondary max-w-2xl mx-auto leading-relaxed">
          In-depth guides on brand equity, conversion psychology, 3D web engineering, and commercial design strategy written by founders Bilal & Shahwaiz.
        </p>

        {/* 2. FILTERS & SEARCH (HORIZONTALLY SCROLLABLE TABS) */}
        <div className="mt-10 max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="w-full md:flex-1 min-w-0">
            <HorizontalScrollTabs
              tabs={['All', ...categories.map((c) => c.name)]}
              activeTab={selectedName}
              onTabChange={(name) => setCategory(categories.find((c) => c.name === name)?.slug || '')}
              centerOnDesktop={false}
            />
          </div>

          <div className="relative w-full md:w-64 shrink-0">
            <Search className="w-4 h-4 text-aub-text-secondary absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search articles..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              aria-label="Search articles"
              className="w-full pl-9 pr-4 py-2.5 min-h-[44px] rounded-full bg-aub-card/80 backdrop-blur-md border border-aub-border text-base sm:text-xs text-white placeholder-white/30 focus:outline-none focus:border-aub-magenta transition-colors shadow-inner"
            />
          </div>
        </div>
      </section>

      {/* 3. FEATURED HERO ARTICLE (if category is All and no search) */}
      {featuredArticle && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-12">
          <Link to={`/blog/${featuredArticle.slug}`} className="block group">
            <GlassCard className="p-6 sm:p-10 border-aub-purple/40 hover:border-aub-magenta/60">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                <div className="lg:col-span-7 h-64 sm:h-96 rounded-2xl overflow-hidden bg-aub-card relative">
                  <img
                    src={featuredArticle.featuredImage}
                    alt={featuredArticle.featuredAlt || featuredArticle.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                  />
                  <div className="absolute top-4 left-4 px-3 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-xs font-semibold text-white">
                    Featured Guide · {featuredArticle.category}
                  </div>
                </div>

                <div className="lg:col-span-5 space-y-4">
                  <div className="flex items-center gap-4 text-xs text-aub-text-secondary">
                    <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5 text-aub-magenta" /> {featuredArticle.publishDate}</span>
                    <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-aub-purple" /> {featuredArticle.readingTime}</span>
                  </div>

                  <h2 className="text-2xl sm:text-3xl font-bold text-white group-hover:text-aub-magenta transition-colors font-display leading-tight">
                    {featuredArticle.title}
                  </h2>

                  <p className="text-sm text-aub-text-secondary leading-relaxed">
                    {featuredArticle.excerpt}
                  </p>

                  <div className="pt-4 flex items-center justify-between border-t border-aub-border/60">
                    <div className="flex items-center gap-3">
                      <Avatar src={featuredArticle.author.avatar} name={featuredArticle.author.name} />
                      <div>
                        <span className="text-xs font-bold text-white block">{featuredArticle.author.name}</span>
                        <span className="text-[10px] text-aub-accent-labels">{featuredArticle.author.role}</span>
                      </div>
                    </div>

                    <span className="text-xs font-semibold text-aub-magenta inline-flex items-center gap-1 group-hover:translate-x-1 transition-transform">
                      Read Full Article <ArrowRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              </div>
            </GlassCard>
          </Link>
        </section>
      )}

      {/* 4. ARTICLES GRID */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <h3 className="text-xl font-bold text-white font-display">
            {tag ? `Tagged “${tag}”` : selectedName === 'All' ? 'All Published Articles' : `${selectedName} Articles`}
          </h3>
          <span className="text-xs text-aub-text-secondary font-mono">
            {count} article{count === 1 ? '' : 's'}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <AnimatePresence>
            {filteredArticles.map((article, idx) => (
              <motion.div
                key={article.id}
                layout
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: idx * 0.05 }}
              >
                <Link to={`/blog/${article.slug}`} className="block group h-full">
                  <GlassCard className="h-full flex flex-col p-5 hover:border-aub-magenta/50">
                    <div className="relative w-full h-52 rounded-xl overflow-hidden mb-4 bg-aub-card">
  <RevealImage src={article.featuredImage} alt={article.featuredAlt || article.title} />
                      <div className="absolute inset-0 bg-gradient-to-t from-[#0B0B12]/80 via-transparent to-transparent" />
                      <div className="absolute top-3 left-3 px-3 py-1 rounded-full bg-black/60 backdrop-blur-md border border-white/20 text-xs font-semibold text-white">
                        {article.category}
                      </div>
                    </div>

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

                    <div className="flex-1 flex flex-col justify-between">
                      <div>
                        <h4 className="text-lg font-bold text-white group-hover:text-aub-magenta transition-colors line-clamp-2 font-display mb-2">
                          {article.title}
                        </h4>
                        <p className="text-xs sm:text-sm text-aub-text-secondary line-clamp-2 leading-relaxed">
                          {article.excerpt}
                        </p>
                      </div>

                      <div className="mt-5 pt-4 border-t border-aub-border/60 flex items-center justify-between text-xs font-semibold text-aub-accent-labels group-hover:text-white transition-colors">
                        <span>Read Article</span>
                        <ArrowRight className="w-4 h-4 text-aub-magenta group-hover:translate-x-1 transition-transform" />
                      </div>
                    </div>
                  </GlassCard>
                </Link>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* Load More Button */}
        {!loading && !error && items.length === 0 && (
          <div className="text-center py-16 text-sm text-aub-text-secondary">No articles match your search yet.</div>
        )}
        {error && <div role="alert" className="text-center py-8 text-sm text-red-300">{error}</div>}
        {loading && items.length === 0 && <div className="text-center py-16 text-sm text-aub-text-secondary" role="status">Loading articles…</div>}
        {hasMore && (
          <div className="mt-12 text-center">
            <button
              disabled={loading}
              onClick={loadMore}
              className="px-8 py-3.5 rounded-full glass-panel border border-aub-border hover:border-aub-magenta text-white font-semibold text-sm hover:bg-white/5 transition-all"
            >
              Load More Articles
            </button>
          </div>
        )}
      </section>

      {/* 5. NEWSLETTER SIGNUP */}
      <section className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-16">
        <GlassCard className="p-8 sm:p-12 border-aub-purple/50 text-center">
          <div className="w-12 h-12 rounded-2xl bg-aub-gradient flex items-center justify-center mx-auto mb-4 text-white shadow-glow-magenta">
            <Mail className="w-6 h-6" />
          </div>
          <h3 className="text-2xl sm:text-3xl font-bold text-white font-display mb-2">
            Subscribe to The Creative Advantage
          </h3>
          <p className="text-xs sm:text-sm text-aub-text-secondary max-w-md mx-auto mb-6">
            A bi-weekly newsletter with actionable brand strategy breakdowns and 3D web trends delivered directly to your inbox.
          </p>

          {nlState.status === 'ok' ? (
            <div role="status" className="p-4 rounded-xl bg-green-500/20 border border-green-500/40 text-green-300 text-xs sm:text-sm flex items-center justify-center gap-2 max-w-md mx-auto">
              <CheckCircle2 className="w-4 h-4" />
              <span>{nlState.msg}</span>
            </div>
          ) : (
            <form onSubmit={handleNewsletter} className="flex flex-col gap-3 max-w-md mx-auto text-left">
              <div className="flex flex-col sm:flex-row gap-3">
                <input
                  type="email"
                  placeholder="your.email@company.com"
                  value={newsletterEmail}
                  onChange={e => setNewsletterEmail(e.target.value)}
                  required
                  aria-label="Email address"
                  autoComplete="email"
                  className="flex-1 min-h-[48px] px-4 py-3 rounded-full bg-aub-card border border-aub-border text-white text-base sm:text-sm placeholder-white/30 focus:outline-none focus:border-aub-magenta"
                />
                <button
                  type="submit"
                  disabled={nlState.status === 'busy'}
                  className="min-h-[48px] px-6 py-3 rounded-full bg-aub-gradient text-white font-bold text-xs sm:text-sm shadow-glow-magenta hover:shadow-glow-purple transition-all disabled:opacity-60"
                >
                  {nlState.status === 'busy' ? 'Subscribing…' : 'Subscribe'}
                </button>
              </div>
              <label className="flex items-start gap-2 text-[11px] text-aub-text-secondary">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} required className="mt-0.5 accent-[#EC008C]" />
                <span>I agree to receive the newsletter by email. I can unsubscribe at any time.</span>
              </label>
              <input type="text" name="website" value={website} onChange={(e) => setWebsite(e.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" />
              {nlState.status === 'err' && <p role="alert" className="text-xs text-red-300">{nlState.msg}</p>}
            </form>
          )}
        </GlassCard>
      </section>
    </div>
  );
};
