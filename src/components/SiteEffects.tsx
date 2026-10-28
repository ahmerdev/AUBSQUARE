import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../lib/api';
import { useSite } from '../context/CmsContext';
import { localMedia } from '../lib/media';
import { inPreviewFrame, setSitePreview, trustedParent } from '../lib/brandPreview';

/**
 * Route-level side effects that need no UI:
 *  - keeps <title>, meta description, canonical, robots, Open Graph and JSON-LD in sync with the server's SEO resolver on client-side navigation
 *    (first paint is already correct because Django injects the same metadata into the served HTML);
 *  - sends one privacy-friendly page view per route change (the server ignores Do-Not-Track / Global Privacy Control and bots, and stores no IP).
 */
interface SeoMeta { title: string; description: string; canonical: string; robots: string; og: Record<string, string>; jsonld: unknown[] }
const cache = new Map<string, SeoMeta>();

function setMeta(attr: 'name' | 'property', key: string, value?: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!value) { el?.remove(); return; }
  if (!el) { el = document.createElement('meta'); el.setAttribute(attr, key); document.head.appendChild(el); }
  el.setAttribute('content', value);
}

function applyMeta(m: SeoMeta) {
  if (m.title) document.title = m.title;
  setMeta('name', 'description', m.description);
  setMeta('name', 'robots', m.robots);
  let link = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (m.canonical) {
    if (!link) { link = document.createElement('link'); link.rel = 'canonical'; document.head.appendChild(link); }
    link.href = m.canonical;
  } else link?.remove();
  const og = m.og || {};
  setMeta('property', 'og:title', og.title);
  setMeta('property', 'og:description', og.description);
  setMeta('property', 'og:image', og.image);
  setMeta('property', 'og:url', og.url);
  setMeta('property', 'og:type', og.type);
  setMeta('property', 'og:site_name', og.site_name);
  setMeta('name', 'twitter:card', og.image ? 'summary_large_image' : 'summary');
  document.head.querySelectorAll('script[data-aub-jsonld]').forEach((n) => n.remove());
  (m.jsonld || []).forEach((obj) => {
    const s = document.createElement('script');
    s.type = 'application/ld+json';
    s.setAttribute('data-aub-jsonld', '1');
    s.textContent = JSON.stringify(obj).replace(/</g, '\\u003c');
    document.head.appendChild(s);
  });
}

function setIcon(rel: string, href: string) {
  let link = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!link) { link = document.createElement('link'); link.rel = rel; document.head.appendChild(link); }
  link.removeAttribute('type');
  link.href = href;
}

/* ---------- fonts chosen in Dashboard → Branding ---------- */
const FONT_CSS = /^https:\/\/fonts\.googleapis\.com\/css2\?[A-Za-z0-9+:;=&@.,%_-]+$/;
const FONT_STACK = /^[\w\s",.\-]{3,300}$/;

function setFontVars(heading: string, body: string) {
  if (!FONT_STACK.test(heading) || !FONT_STACK.test(body)) return;
  let st = document.getElementById('aub-fonts') as HTMLStyleElement | null;
  if (!st) { st = document.createElement('style'); st.id = 'aub-fonts'; document.head.appendChild(st); }
  const css = `:root{--font-heading:${heading};--font-body:${body}}`;
  if (st.textContent !== css) st.textContent = css;
}
function loadFontCss(id: string, href: string) {
  if (!FONT_CSS.test(href)) return;
  let link = document.getElementById(id) as HTMLLinkElement | null;
  if (!link) { link = document.createElement('link'); link.id = id; link.rel = 'stylesheet'; document.head.appendChild(link); }
  if (link.getAttribute('href') !== href) link.setAttribute('href', href);
}

export const SiteEffects: React.FC = () => {
  const { pathname, search } = useLocation();
  const site = useSite();

  // Browser-tab icon: the favicon set in Website settings, else the logo, else the built-in one.
  useEffect(() => {
    const icon = localMedia(site.favicon) || localMedia(site.logo);
    if (!icon) return;
    setIcon('icon', icon);
    setIcon('apple-touch-icon', icon);
  }, [site.favicon, site.logo]);

  // Fonts: the server already put the right <link>/<style> in the page; this keeps them current after a dashboard change (no reload needed).
  useEffect(() => {
    const f = site.fonts;
    if (!f) return;
    if (f.cssUrl) loadFontCss('aub-font-link', f.cssUrl);
    setFontVars(f.headingStack, f.bodyStack);
  }, [site.fonts]);

  // Live preview inside the dashboard: show unsaved branding choices without saving anything.
  // Works when the site is served by Django (same origin) and when it runs on the React dev server (e.g. localhost:3000)
  // next to the dashboard (127.0.0.1:8000). Only the direct parent window of a local/same-origin/API-origin dashboard is trusted.
  useEffect(() => {
    if (!inPreviewFrame()) return;
    const onMsg = (e: MessageEvent) => {
      if (e.source !== window.parent || !trustedParent(e.origin)) return;
      const d = e.data;
      if (!d || d.type !== 'aub-brand-preview' || typeof d.payload !== 'object' || d.payload === null) return;
      const p = d.payload as Record<string, unknown>;
      (Array.isArray(p.fontLinks) ? p.fontLinks : []).slice(0, 2).forEach((u, i) => { if (typeof u === 'string') loadFontCss(`aub-preview-font-${i}`, u); });
      if (typeof p.headingStack === 'string' && typeof p.bodyStack === 'string') setFontVars(p.headingStack, p.bodyStack);
      const next: Record<string, unknown> = {};
      if (typeof p.logo === 'string') next.logo = p.logo;
      if (typeof p.siteName === 'string') next.siteName = p.siteName.slice(0, 80);
      if (typeof p.headerShowName === 'boolean') next.headerShowName = p.headerShowName;
      setSitePreview(next);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: 'aub-preview-ready' }, '*'); // carries no data; the dashboard checks who sent it
    return () => window.removeEventListener('message', onMsg);
  }, []);

  useEffect(() => {
    let alive = true;
    const hit = cache.get(pathname);
    if (hit) applyMeta(hit);
    else
      api<SeoMeta>(`/seo/?path=${encodeURIComponent(pathname)}`)
        .then((m) => { cache.set(pathname, m); if (alive) applyMeta(m); })
        .catch(() => { /* offline: keep whatever the HTML shipped with */ });
    return () => { alive = false; };
  }, [pathname]);

  useEffect(() => {
    if (inPreviewFrame()) return; // the dashboard's preview frame must never count as a visit
    const q = new URLSearchParams(search);
    const t = window.setTimeout(() => {
      api('/analytics/pageview/', {
        method: 'POST',
        keepalive: true,
        json: {
          path: pathname,
          referrer: document.referrer || '',
          utm_source: q.get('utm_source') || '', utm_medium: q.get('utm_medium') || '', utm_campaign: q.get('utm_campaign') || '',
        },
      }).catch(() => {});
    }, 800);
    return () => window.clearTimeout(t);
  }, [pathname, search]);

  return null;
};
