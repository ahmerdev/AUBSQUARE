import { useEffect, useState } from 'react';
import { api, Paginated } from './api';
import type { Article } from '../types';
import { articlesData } from '../data/articles';

interface Params { category: string; tag: string; q: string }
interface State { items: Article[]; page: number; pages: number; count: number; loading: boolean; error: string; offline: boolean }

/**
 * Server-side filtered, paginated article list (page size 9). Falls back to the static articles, filtered in the browser, if the API is unreachable.
 * `loadMore` appends the next page. Changing a filter resets to page 1.
 */
export function useArticleList({ category, tag, q }: Params) {
  const [st, setSt] = useState<State>({ items: [], page: 0, pages: 1, count: 0, loading: true, error: '', offline: false });
  const [wanted, setWanted] = useState(1);
  const key = `${category}|${tag}|${q}`;

  useEffect(() => { setWanted(1); }, [key]);

  useEffect(() => {
    const ctl = new AbortController();
    const qs = new URLSearchParams({ page: String(wanted), page_size: '9' });
    if (category) qs.set('category', category);
    if (tag) qs.set('tag', tag);
    if (q) qs.set('q', q);
    setSt((s) => ({ ...s, loading: true, error: '' }));
    const t = window.setTimeout(() => {
      api<Paginated<Article>>(`/posts/?${qs}`, { signal: ctl.signal })
        .then((res) =>
          setSt((s) => ({ items: wanted === 1 ? res.results : [...s.items, ...res.results], page: res.page || wanted, pages: res.pages || 1, count: res.count, loading: false, error: '', offline: false })),
        )
        .catch((e) => {
          if ((e as Error).name === 'AbortError') return;
          if ((e as { status?: number }).status === 0) {
            const term = q.toLowerCase();
            const list = articlesData.filter((a) => (!category || a.category.toLowerCase().replace(/\s+/g, '-') === category) && (!term || a.title.toLowerCase().includes(term) || a.excerpt.toLowerCase().includes(term)));
            setSt({ items: list, page: 1, pages: 1, count: list.length, loading: false, error: '', offline: true });
          } else setSt((s) => ({ ...s, loading: false, error: (e as Error).message }));
        });
    }, q ? 300 : 0); // debounce typing
    return () => { window.clearTimeout(t); ctl.abort(); };
  }, [key, wanted]); // eslint-disable-line react-hooks/exhaustive-deps

  return { ...st, hasMore: st.page < st.pages, loadMore: () => setWanted((w) => w + 1) };
}
