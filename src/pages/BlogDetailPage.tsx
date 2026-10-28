import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Calendar,
  Clock,
  Share2,
  MessageSquare,
  CheckCircle2,
  Send,
  User,
  AlertCircle,
} from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';
import { Comment, Article } from '../types';
import { api, ApiError, previewQuery } from '../lib/api';
import { articlesData } from '../data/articles';
import { NotFoundPage } from './NotFoundPage';

type Load = { status: 'loading' } | { status: 'notfound' } | { status: 'ready'; article: Article };

const fmtWhen = (iso: string) => {
  const d = new Date(iso);
  return isNaN(+d) ? iso : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

const CommentNode: React.FC<{ c: Comment; depth?: number; onReply: (c: Comment) => void; canReply: boolean }> = ({ c, depth = 0, onReply, canReply }) => (
  <div className={depth ? 'ml-4 sm:ml-8 border-l border-aub-border/60 pl-4' : ''}>
    <div className="p-5 rounded-2xl bg-aub-card/60 border border-aub-border space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-bold text-white flex items-center gap-1.5">
          <User className="w-3.5 h-3.5 text-aub-accent-labels" />
          {c.authorName}
          {c.isStaff && <span className="px-1.5 py-0.5 rounded bg-aub-magenta/20 text-aub-magenta text-[10px] uppercase tracking-wider">Team</span>}
        </span>
        <span className="text-aub-text-secondary">{fmtWhen(c.createdAt)}</span>
      </div>
      <p className="text-xs sm:text-sm text-aub-text-secondary leading-relaxed whitespace-pre-wrap break-words">{c.message}</p>
      {canReply && depth === 0 && (
        <button type="button" onClick={() => onReply(c)} className="text-[11px] font-semibold text-aub-accent-labels hover:text-white">Reply</button>
      )}
    </div>
    {(c.replies || []).map((r) => (
      <div key={r.id} className="mt-3"><CommentNode c={r} depth={depth + 1} onReply={onReply} canReply={false} /></div>
    ))}
  </div>
);

export const BlogDetailPage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const [load, setLoad] = useState<Load>({ status: 'loading' });

  useEffect(() => {
    if (!slug) return;
    const ctl = new AbortController();
    setLoad({ status: 'loading' });
    api<Article>(`/posts/${encodeURIComponent(slug)}/${previewQuery()}`, { signal: ctl.signal })
      .then((article) => setLoad({ status: 'ready', article }))
      .catch((e: ApiError) => {
        if (e.name === 'AbortError') return;
        if (e.status === 0) {
          const local = articlesData.find((a) => a.slug === slug); // API unreachable: show the bundled article
          setLoad(local ? { status: 'ready', article: local } : { status: 'notfound' });
        } else setLoad({ status: 'notfound' });
      });
    return () => ctl.abort();
  }, [slug]);

  // Reading progress
  const [scrollProgress, setScrollProgress] = useState(0);
  useEffect(() => {
    const handleScroll = () => {
      const total = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      setScrollProgress(total > 0 ? (document.documentElement.scrollTop / total) * 100 : 0);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Comments (server-moderated: a new comment is held until a staff member approves it)
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentsOpen, setCommentsOpen] = useState(true);
  const [commentCount, setCommentCount] = useState(0);
  const [authorName, setAuthorName] = useState('');
  const [authorEmail, setAuthorEmail] = useState('');
  const [commentText, setCommentText] = useState('');
  const [website, setWebsite] = useState(''); // honeypot
  const [replyTo, setReplyTo] = useState<Comment | null>(null);
  const [commentError, setCommentError] = useState('');
  const [commentSuccess, setCommentSuccess] = useState('');
  const [sending, setSending] = useState(false);
  const [formToken, setFormToken] = useState('');

  const article = load.status === 'ready' ? load.article : null;
  const isCms = !!article?.contentHtml;

  const loadComments = useCallback(() => {
    if (!slug || !isCms) return;
    api<{ allowComments: boolean; count: number; comments: Comment[] }>(`/posts/${encodeURIComponent(slug)}/comments/${previewQuery()}`)
      .then((r) => { setComments(r.comments); setCommentCount(r.count); setCommentsOpen(r.allowComments); })
      .catch(() => {});
  }, [slug, isCms]);

  useEffect(() => {
    loadComments();
    if (isCms) api<{ token: string }>('/form-token/').then((r) => setFormToken(r.token)).catch(() => {});
  }, [loadComments, isCms]);

  const handleCommentSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCommentError(''); setCommentSuccess('');
    if (!authorName.trim() || !authorEmail.trim() || !commentText.trim()) return setCommentError('Please fill out all fields.');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(authorEmail)) return setCommentError('Please enter a valid email address.');
    setSending(true);
    try {
      let token = formToken;
      if (!token) token = (await api<{ token: string }>('/form-token/')).token;
      const r = await api<{ message: string }>(`/posts/${encodeURIComponent(slug!)}/comments/`, {
        method: 'POST',
        json: { name: authorName.trim(), email: authorEmail.trim(), message: commentText.trim(), parentId: replyTo?.id, formToken: token, website },
      });
      setCommentSuccess(r.message);
      setAuthorName(''); setAuthorEmail(''); setCommentText(''); setReplyTo(null);
      api<{ token: string }>('/form-token/').then((t) => setFormToken(t.token)).catch(() => {});
    } catch (err) {
      const ae = err as ApiError;
      const first = ae.details ? Object.values(ae.details)[0] : '';
      setCommentError((Array.isArray(first) ? first[0] : first) || ae.message || 'Could not post your comment. Please try again.');
    } finally {
      setSending(false);
    }
  };

  const [copied, setCopied] = useState(false);
  const handleShare = () => {
    if (!article) return;
    if (navigator.share) navigator.share({ title: article.title, url: window.location.href }).catch(() => {});
    else navigator.clipboard?.writeText(window.location.href).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 2000); }).catch(() => {});
  };

  if (load.status === 'loading') return <div className="pt-40 pb-40 text-center text-aub-text-secondary text-sm" role="status">Loading article…</div>;
  if (load.status === 'notfound' || !article) return <NotFoundPage />;

  const relatedArticles = (article.related && article.related.length ? article.related : articlesData.filter((a) => a.id !== article.id)).slice(0, 2);
  const authorInitial = (article.author?.name || 'A').slice(0, 1);

  return (
    <div className="relative pt-24 sm:pt-28 pb-20">
      {/* Scroll Reading Progress Indicator */}
      <div className="fixed top-0 left-0 h-1 bg-aub-gradient z-50 transition-all duration-150" style={{ width: `${scrollProgress}%` }} />

      {/* 1. TOP BREADCRUMB */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-6">
        <Link to="/blog" className="inline-flex items-center gap-2 text-xs font-semibold text-aub-accent-labels hover:text-white transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <span>Back to All Articles</span>
        </Link>
      </div>

      {/* 2. ARTICLE HEADER */}
      <article className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={article.categorySlug ? `/blog/category/${article.categorySlug}` : '/blog'} className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-aub-card border border-aub-border text-xs font-semibold uppercase tracking-wider text-aub-magenta">
              <span>{article.category}</span>
            </Link>
            {(article.tags || []).map((t) => (
              <Link key={t.slug} to={`/blog/tag/${t.slug}`} className="px-2.5 py-1 rounded-full border border-aub-border/70 text-[11px] text-aub-text-secondary hover:text-white">#{t.name}</Link>
            ))}
          </div>

          <h1 className="fluid-h1 font-extrabold text-white font-display">{article.title}</h1>
          {article.excerpt && <p className="text-base sm:text-lg text-aub-text-secondary leading-relaxed pt-2">{article.excerpt}</p>}

          {/* Author Meta Bar */}
          <div className="pt-4 pb-6 border-b border-aub-border/60 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {article.author.avatar ? (
                <img src={article.author.avatar} alt={article.author.name} className="w-11 h-11 rounded-full object-cover border-2 border-aub-magenta" />
              ) : (
                <span className="w-11 h-11 rounded-full bg-aub-gradient text-white font-bold flex items-center justify-center" aria-hidden="true">{authorInitial}</span>
              )}
              <div>
                <span className="text-sm font-bold text-white block">{article.author.name}</span>
                <span className="text-xs text-aub-accent-labels">{article.author.role}</span>
              </div>
            </div>

            <div className="flex items-center gap-5 text-xs text-aub-text-secondary">
              <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4 text-aub-magenta" /> {article.publishDate}</span>
              <span className="flex items-center gap-1.5"><Clock className="w-4 h-4 text-aub-purple" /> {article.readingTime}</span>
              <button onClick={handleShare} className="w-8 h-8 rounded-full glass-panel flex items-center justify-center text-white hover:text-aub-magenta transition-colors" aria-label={copied ? 'Link copied' : 'Share article'} title={copied ? 'Link copied' : 'Share'}>
                {copied ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Share2 className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>

        {/* Featured Image */}
        {article.featuredImage && (
          <div className="my-8 rounded-3xl overflow-hidden border border-aub-border shadow-2xl h-[340px] sm:h-[480px]">
            <img src={article.featuredImage} alt={article.featuredAlt || article.title} className="w-full h-full object-cover" />
          </div>
        )}

        {/* 3. TABLE OF CONTENTS */}
        {article.tableOfContents && article.tableOfContents.length > 1 && (
          <nav aria-label="Table of contents" className="p-6 rounded-2xl glass-panel border border-aub-border/80 my-8">
            <h3 className="text-xs font-bold uppercase tracking-wider text-aub-accent-labels mb-3">Table of Contents</h3>
            <ul className="space-y-2">
              {article.tableOfContents.map((item) => (
                <li key={item.id}>
                  <a href={`#${item.id}`} className="text-xs sm:text-sm text-aub-text-secondary hover:text-white transition-colors flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-aub-magenta" />
                    <span>{item.title}</span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        )}

        {/* 4. ARTICLE BODY CONTENT */}
        {isCms ? (
          <div className="cms-prose pt-4" dangerouslySetInnerHTML={{ __html: article.contentHtml! }} />
        ) : (
          <div className="space-y-12 text-aub-text-secondary text-base sm:text-lg leading-relaxed pt-4">
            {article.content.map((section) => (
              <div key={section.sectionId} id={section.sectionId} className="space-y-4 scroll-mt-28">
                <h2 className="text-2xl sm:text-3xl font-bold text-white font-display tracking-tight pt-2">{section.heading}</h2>
                {section.paragraphs.map((p, i) => (<p key={i} className="text-sm sm:text-base leading-relaxed text-aub-text-secondary">{p}</p>))}
                {section.pullQuote && (<div className="my-6 p-6 rounded-2xl border-l-4 border-aub-magenta bg-aub-card/80 italic text-white text-base sm:text-lg font-display">"{section.pullQuote}"</div>)}
                {section.keyPoints && (
                  <div className="p-5 rounded-xl bg-aub-card/40 border border-aub-border space-y-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-aub-accent-labels">Key Takeaways:</span>
                    <ul className="space-y-1.5">
                      {section.keyPoints.map((kp, i) => (
                        <li key={i} className="flex items-start gap-2 text-xs sm:text-sm text-white"><CheckCircle2 className="w-4 h-4 text-aub-magenta shrink-0 mt-0.5" /><span>{kp}</span></li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 5. COMMENTS SECTION */}
        {isCms && commentsOpen && (
        <section className="mt-16 pt-12 border-t border-aub-border/80 space-y-8" aria-labelledby="comments-h">
          <h3 id="comments-h" className="text-2xl font-bold text-white font-display flex items-center gap-2">
            <MessageSquare className="w-6 h-6 text-aub-magenta" />
            <span>Discussion ({commentCount})</span>
          </h3>

          <GlassCard className="p-6 sm:p-8 border-aub-purple/40">
            <h4 className="text-lg font-bold text-white font-display mb-2">{replyTo ? `Reply to ${replyTo.authorName}` : 'Leave a Thought or Question'}</h4>
            <p className="text-xs text-aub-text-secondary mb-4">
              Your email stays private. Comments are reviewed before they appear.
              {replyTo && <button type="button" onClick={() => setReplyTo(null)} className="ml-2 underline">Cancel reply</button>}
            </p>

            {commentSuccess && (
              <div role="status" className="mb-4 p-3 rounded-xl bg-green-500/20 border border-green-500/40 text-green-300 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /><span>{commentSuccess}</span>
              </div>
            )}
            {commentError && (
              <div role="alert" className="mb-4 p-3 rounded-xl bg-red-500/20 border border-red-500/40 text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4" /><span>{commentError}</span>
              </div>
            )}

            <form onSubmit={handleCommentSubmit} className="space-y-4" noValidate>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <input type="text" placeholder="Your Name *" aria-label="Your name" autoComplete="name" maxLength={80} value={authorName} onChange={(e) => setAuthorName(e.target.value)}
                  className="px-4 py-2.5 min-h-[44px] rounded-xl bg-aub-card border border-aub-border text-white text-base sm:text-sm placeholder-white/30 focus:outline-none focus:border-aub-magenta" />
                <input type="email" placeholder="Your Email (private) *" aria-label="Your email" autoComplete="email" value={authorEmail} onChange={(e) => setAuthorEmail(e.target.value)}
                  className="px-4 py-2.5 min-h-[44px] rounded-xl bg-aub-card border border-aub-border text-white text-base sm:text-sm placeholder-white/30 focus:outline-none focus:border-aub-magenta" />
              </div>
              <textarea rows={3} maxLength={2000} placeholder="Share your perspective or questions on this article..." aria-label="Your comment" value={commentText} onChange={(e) => setCommentText(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-aub-card border border-aub-border text-white text-base sm:text-sm placeholder-white/30 focus:outline-none focus:border-aub-magenta resize-none" />
              <input type="text" name="website" value={website} onChange={(e) => setWebsite(e.target.value)} tabIndex={-1} autoComplete="off" aria-hidden="true" className="hidden" />
              <button type="submit" disabled={sending} className="px-6 py-2.5 min-h-[44px] rounded-full bg-aub-gradient text-white font-bold text-xs sm:text-sm shadow-glow-magenta hover:shadow-glow-purple transition-all inline-flex items-center gap-2 disabled:opacity-60">
                <Send className="w-3.5 h-3.5" />
                <span>{sending ? 'Sending…' : 'Post Comment'}</span>
              </button>
            </form>
          </GlassCard>

          <div className="space-y-4">
            {comments.length === 0 && <p className="text-sm text-aub-text-secondary">No comments yet. Be the first to share a thought.</p>}
            {comments.map((c) => (
              <CommentNode key={c.id} c={c} canReply onReply={(x) => { setReplyTo(x); setCommentSuccess(''); }} />
            ))}
          </div>
        </section>
        )}

        {/* 6. RELATED ARTICLES */}
        {relatedArticles.length > 0 && (
        <section className="mt-16 pt-12 border-t border-aub-border/80">
          <h3 className="text-xl font-bold text-white font-display mb-6">Related Articles</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {relatedArticles.map((rel) => (
              <Link key={rel.id} to={`/blog/${rel.slug}`} className="block group">
                <GlassCard className="p-5 flex gap-4 items-center hover:border-aub-magenta/50">
                  <div className="w-24 h-20 rounded-xl overflow-hidden bg-aub-card shrink-0">
                    {rel.featuredImage && <img src={rel.featuredImage} alt={rel.featuredAlt || rel.title} loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition-transform" />}
                  </div>
                  <div>
                    <span className="text-[10px] text-aub-magenta font-semibold uppercase">{rel.category}</span>
                    <h4 className="text-xs sm:text-sm font-bold text-white group-hover:text-aub-magenta transition-colors line-clamp-2 mt-0.5">{rel.title}</h4>
                  </div>
                </GlassCard>
              </Link>
            ))}
          </div>
        </section>
        )}
      </article>
    </div>
  );
};
