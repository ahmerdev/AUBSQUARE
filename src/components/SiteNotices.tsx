import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Megaphone, X } from 'lucide-react';
import { isExternal, useCms } from '../context/CmsContext';

const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage blocked: notice simply returns next visit */ } };

/** Announcement banner and cookie/privacy notice, both controlled from the dashboard (Site settings / Banners). */
export const SiteNotices: React.FC = () => {
  const { data } = useCms();
  const banner = data?.banner;
  const cookie = data?.site.cookieNotice;
  const [bannerHidden, setBannerHidden] = useState(true);
  const [cookieHidden, setCookieHidden] = useState(true);

  useEffect(() => { setBannerHidden(!banner || (banner.dismissible && read(`aub_banner_${banner.id}`) === '1')); }, [banner]);
  useEffect(() => { setCookieHidden(!cookie?.enabled || read('aub_cookie_ok') === '1'); }, [cookie]);

  const link = banner?.linkUrl;
  return (
    <>
      {banner && !bannerHidden && (
        <div role="region" aria-label="Announcement" className="fixed left-1/2 -translate-x-1/2 top-[4.4rem] sm:top-[5rem] z-30 w-[calc(100%-1.5rem)] max-w-2xl">
          <div className={`flex items-center gap-3 rounded-full pl-4 pr-2 py-1.5 text-xs sm:text-[13px] text-white backdrop-blur-xl border shadow-xl ${banner.style === 'warning' ? 'bg-amber-500/25 border-amber-400/50' : banner.style === 'success' ? 'bg-emerald-500/25 border-emerald-400/50' : 'bg-aub-purple/30 border-aub-purple/60'}`}>
            <Megaphone className="w-4 h-4 shrink-0 text-aub-magenta" aria-hidden="true" />
            <span className="flex-1 min-w-0 truncate sm:whitespace-normal">{banner.message}</span>
            {link && banner.linkLabel && (isExternal(link)
              ? <a href={link} className="font-bold underline underline-offset-2 whitespace-nowrap" target="_blank" rel="noopener noreferrer">{banner.linkLabel}</a>
              : <Link to={link} className="font-bold underline underline-offset-2 whitespace-nowrap">{banner.linkLabel}</Link>)}
            {banner.dismissible && (
              <button type="button" aria-label="Dismiss announcement" onClick={() => { write(`aub_banner_${banner.id}`, '1'); setBannerHidden(true); }} className="w-8 h-8 rounded-full flex items-center justify-center hover:bg-white/10 shrink-0">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}
      {cookie?.enabled && !cookieHidden && (
        <div role="dialog" aria-label="Cookie notice" className="fixed left-3 bottom-3 sm:left-5 sm:bottom-5 z-[45] max-w-sm rounded-2xl bg-[#120D24]/95 backdrop-blur-xl border border-aub-border p-4 shadow-2xl">
          <p className="text-xs text-aub-text-secondary leading-relaxed">{cookie.text || 'We use essential cookies and privacy-friendly analytics to run this site.'}
            {data?.site.privacyUrl && <> <a href={data.site.privacyUrl} className="underline text-white">Privacy policy</a></>}</p>
          <button type="button" onClick={() => { write('aub_cookie_ok', '1'); setCookieHidden(true); }} className="mt-3 min-h-[40px] px-5 rounded-full bg-aub-gradient text-white text-xs font-bold">OK, got it</button>
        </div>
      )}
    </>
  );
};
