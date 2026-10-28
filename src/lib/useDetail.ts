import { useEffect, useState } from 'react';
import { api, previewQuery } from './api';

export type DetailState<T> = { status: 'loading' } | { status: 'notfound' } | { status: 'ready'; item: T };

/**
 * Resolve one CMS item by slug.
 *  - normally uses the already-loaded list (no extra request, instant);
 *  - with a `?preview=` token (issued by the dashboard) it asks the API directly so editors can see unpublished drafts;
 *  - falls back to the API when the item is not in the list (e.g. beyond the list's page size).
 */
export function useDetail<T extends { slug?: string }>(kind: 'services' | 'projects' | 'case-studies', slug: string | undefined, list: T[], listReady: boolean): DetailState<T> {
  const preview = previewQuery();
  const local = !preview ? list.find((x) => x.slug === slug) : undefined;
  const [remote, setRemote] = useState<DetailState<T>>({ status: 'loading' });

  useEffect(() => {
    if (local || !slug) return;
    if (!preview && !listReady) return; // wait for the bootstrap first
    const ctl = new AbortController();
    setRemote({ status: 'loading' });
    api<T>(`/${kind}/${encodeURIComponent(slug)}/${preview}`, { signal: ctl.signal })
      .then((item) => setRemote({ status: 'ready', item }))
      .catch((e) => { if ((e as Error).name !== 'AbortError') setRemote({ status: 'notfound' }); });
    return () => ctl.abort();
  }, [kind, slug, preview, local, listReady]);

  if (local) return { status: 'ready', item: local };
  return remote;
}
