import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { useSitePreview } from '../lib/brandPreview';
import type { Article, Bootstrap, NavLink as NavLinkT, CaseStudy, FAQItem, HomeSectionData, Project, Service, SiteInfo, TeamMemberInfo, Testimonial } from '../types';
import { servicesData } from '../data/services';
import { projectsData } from '../data/projects';
import { caseStudiesData } from '../data/caseStudies';
import { articlesData } from '../data/articles';
import { testimonialsData } from '../data/testimonials';
import { faqsData } from '../data/faqs';
import { homeDefaults } from '../data/homeDefaults';

/**
 * CMS data layer.
 *  1. If the server injected the bootstrap JSON into the page (production, via Django), use it immediately: no flash, no request.
 *  2. Otherwise fetch /api/v1/bootstrap/.
 *  3. While loading, or if the API is unreachable (e.g. `npm run dev` without the backend), the original static content is used,
 *     so the site never shows a blank page. Once the API answers, ITS data wins even when a list is empty (unpublished = hidden).
 */
type Status = 'loading' | 'ready' | 'offline';
interface Ctx {
  status: Status;
  data: Bootstrap | null;
  refresh: () => void;
}

const CmsContext = createContext<Ctx>({ status: 'loading', data: null, refresh: () => {} });

function readInjected(): Bootstrap | null {
  try {
    const el = document.getElementById('aub-bootstrap');
    return el?.textContent ? (JSON.parse(el.textContent) as Bootstrap) : null;
  } catch {
    return null;
  }
}

export const CmsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const injected = useMemo(readInjected, []);
  const [data, setData] = useState<Bootstrap | null>(injected);
  const [status, setStatus] = useState<Status>(injected ? 'ready' : 'loading');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (injected && tick === 0) return; // already have fresh server-rendered data
    const ctl = new AbortController();
    api<Bootstrap>('/bootstrap/', { signal: ctl.signal })
      .then((d) => {
        setData(d);
        setStatus('ready');
      })
      .catch((e) => {
        if ((e as Error).name !== 'AbortError') setStatus((s) => (s === 'ready' ? s : 'offline'));
      });
    return () => ctl.abort();
  }, [tick, injected]);

  // Content edited in the dashboard shows up when the visitor/editor returns to this tab (throttled to once per 20 s).
  useEffect(() => {
    let last = Date.now();
    const onBack = () => {
      if (document.visibilityState === 'hidden' || Date.now() - last < 20000) return;
      last = Date.now();
      api<Bootstrap>('/bootstrap/').then((d) => { setData(d); setStatus('ready'); }).catch(() => {});
    };
    document.addEventListener('visibilitychange', onBack);
    window.addEventListener('focus', onBack);
    return () => { document.removeEventListener('visibilitychange', onBack); window.removeEventListener('focus', onBack); };
  }, []);

  const value = useMemo<Ctx>(() => ({ status, data, refresh: () => setTick((t) => t + 1) }), [status, data]);
  return <CmsContext.Provider value={value}>{children}</CmsContext.Provider>;
};

export const useCms = () => useContext(CmsContext);

function pick<T>(live: T[] | undefined, fallback: T[]): T[] {
  return live ?? fallback;
}

export const useServices = (): Service[] => pick(useCms().data?.services, servicesData);
export const useProjects = (): Project[] => pick(useCms().data?.projects, projectsData);
export const useCaseStudies = (): CaseStudy[] => pick(useCms().data?.caseStudies, caseStudiesData);
export const useTestimonials = (): Testimonial[] => pick(useCms().data?.testimonials, testimonialsData);
export const useFaqs = (): FAQItem[] => pick(useCms().data?.faqs, faqsData);
/** Latest posts for the home page / sliders. Full lists with filters use `useArticleList` in BlogPage. */
export const useLatestArticles = (): Article[] => pick(useCms().data?.latestPosts, articlesData);

/** Offline fallback = the contact details that were hard-coded in the original site. */
export const fallbackSite: SiteInfo = {
  siteName: 'AUB SQUARE', tagline: 'Creative agency for startups & small businesses', logo: '', favicon: '',
  contactEmail: 'contact@aubsquare.com', whatsappNumber: '923272755118', phone: '+92-327-2755118', address: '', businessHours: '',
  socials: { linkedin: 'https://www.linkedin.com/company/aubsquare', instagram: 'https://www.instagram.com/aubsquare' },
  footerText: '', copyright: '', ctaLabel: 'Get a Free Quote', ctaUrl: '', cookieNotice: { enabled: false, text: '' },
  privacyUrl: '', termsUrl: '', analytics: { gaId: '', gtmId: '', pixelId: '' }, titleSuffix: ' | AUB SQUARE',
  defaultSeo: { title: 'AUB SQUARE', description: '', ogImage: '' },
};
export const useSite = (): SiteInfo => {
  const base = useCms().data?.site ?? fallbackSite;
  const preview = useSitePreview();
  return preview ? { ...base, ...preview } : base;
};
export const whatsappLink = (site: SiteInfo, text?: string): string => {
  const n = (site.whatsappNumber || '').replace(/\D/g, '');
  return n ? `https://wa.me/${n}${text ? `?text=${encodeURIComponent(text)}` : ''}` : '';
};
export const useTeam = (): TeamMemberInfo[] => useCms().data?.team ?? [];
/** Home sections in display order. Hidden sections are filtered out; the hero is always first. */
export const useHomeSections = (): HomeSectionData[] => {
  const live = useCms().data?.home;
  const list = live && live.length ? live : homeDefaults;
  return list.filter((s) => s.visible);
};

const defaultNav: Record<string, NavLinkT[]> = {
  header: [['Home', '/'], ['Services', '/services'], ['Portfolio', '/portfolio'], ['Case Studies', '/case-studies'], ['About', '/about'], ['Blog', '/blog'], ['Contact', '/contact']].map(([label, url]) => ({ label, url, newTab: false })),
  footer_explore: [['Home', '/'], ['About Us', '/about'], ['Our Services', '/services'], ['Portfolio', '/portfolio'], ['Case Studies', '/case-studies'], ['Insights & Blog', '/blog'], ['Contact', '/contact']].map(([label, url]) => ({ label, url, newTab: false })),
  footer_services: [],
  footer_legal: [],
};
/** Navigation links for header | footer_explore | footer_services | footer_legal (editable in the dashboard). */
export const useNav = (location: 'header' | 'footer_explore' | 'footer_services' | 'footer_legal'): NavLinkT[] => {
  const live = useCms().data?.nav;
  return live ? live[location] ?? [] : defaultNav[location];
};
export const isExternal = (url: string) => /^(https?:)?\/\//i.test(url) || url.startsWith('mailto:') || url.startsWith('tel:');
