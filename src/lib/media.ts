/**
 * The API returns uploaded files as absolute URLs built from the server's SITE_URL. If that setting does not match the address
 * the site is actually opened on (localhost vs. production domain, www vs. non-www, http vs. https), an image would point at a
 * host that cannot serve it. Uploaded files always live under /media/ on the same origin as the site (the Vite dev server proxies
 * /media to Django), so for those we keep only the path. Any other URL (CDN, social avatars…) is left untouched.
 */
export function localMedia(url?: string | null): string {
  if (!url) return '';
  if (url.startsWith('/')) return url;
  try {
    const u = new URL(url, window.location.origin);
    if (u.pathname.startsWith('/media/')) return u.pathname + u.search;
  } catch {
    /* not a URL – fall through */
  }
  return url;
}
