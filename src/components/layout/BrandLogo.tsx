import React, { useEffect, useState } from 'react';
import { useSite } from '../../context/CmsContext';
import { localMedia } from '../../lib/media';

/**
 * The site's logo, driven by Dashboard → Website settings → Brand.
 *  - A logo image uploaded there replaces the built-in mark everywhere (header, footer, mobile menu).
 *  - If no logo is set, or the image fails to load, the original gradient "AUB" mark is shown so the header never breaks.
 *  - The site name comes from the same settings ("AUB SQUARE" keeps its two-tone styling).
 */
const initialsOf = (name: string) => {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length > 1) return words.slice(0, 3).map((w) => w[0]).join('').toUpperCase();
  return name.trim().slice(0, 3).toUpperCase() || 'AUB';
};

export const useBrand = () => {
  const site = useSite();
  const name = (site.siteName || 'AUB SQUARE').trim();
  const logo = localMedia(site.logo);
  const words = name.split(/\s+/);
  const first = words[0] || name;
  const rest = words.slice(1).join('');
  return { site, name, logo, first, rest, initials: initialsOf(name), isDefault: name.toUpperCase().replace(/\s+/g, '') === 'AUBSQUARE' };
};

export const BrandName: React.FC<{ className?: string }> = ({ className = '' }) => {
  const b = useBrand();
  return (
    <span className={className}>
      {b.first.toUpperCase()}
      {b.rest && <span className="text-aub-magenta ml-0.5">{b.rest.toUpperCase()}</span>}
    </span>
  );
};

export const BrandMark: React.FC<{ size?: 'sm' | 'md'; className?: string }> = ({ size = 'md', className = '' }) => {
  const b = useBrand();
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [b.logo]);
  const box = size === 'sm' ? 'w-8 h-8 sm:w-9 sm:h-9' : 'w-10 h-10 sm:w-11 sm:h-11';

  if (b.logo && !failed) {
    return (
      <div className={`${box} rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center overflow-hidden shrink-0 transition-transform duration-300 group-hover:scale-105 ${className}`}>
        <img
          src={b.logo}
          alt={`${b.name} logo`}
          className="w-full h-full object-contain p-1"
          decoding="async"
          onError={() => setFailed(true)}
        />
      </div>
    );
  }
  return (
    <div className={`${box} rounded-xl bg-gradient-to-br from-[#1E173D] via-[#140E29] to-[#0B0B12] border border-aub-magenta/40 group-hover:border-aub-magenta flex items-center justify-center relative overflow-hidden transition-all duration-300 group-hover:scale-105 shrink-0 ${className}`}>
      <div className="absolute inset-0 bg-aub-gradient opacity-20 group-hover:opacity-40 transition-opacity" />
      <div className="relative font-display font-black text-xs sm:text-sm text-white flex items-center justify-center tracking-tighter">
        {b.isDefault ? (<><span className="text-gradient">A</span>UB</>) : <span className="text-gradient">{b.initials}</span>}
      </div>
    </div>
  );
};

/**
 * Brand block for the website header and the mobile menu.
 *  - With an uploaded logo: only the logo is shown (the company name stays as its accessible label) unless
 *    "Show company name next to the logo" is switched on in Dashboard → Branding.
 *  - Without a logo (or if it fails to load): the built-in mark + name, so the header is never empty.
 */
export const HeaderBrand: React.FC<{ variant?: 'header' | 'sheet' }> = ({ variant = 'header' }) => {
  const b = useBrand();
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [b.logo]);
  const sheet = variant === 'sheet';

  if (b.logo && !failed) {
    return (
      <>
        <img
          src={b.logo}
          alt={b.site.headerShowName ? '' : `${b.name} logo`}
          className={`${sheet ? 'h-9 max-w-[170px]' : 'h-9 sm:h-11 max-w-[150px] sm:max-w-[210px]'} w-auto object-contain object-left shrink-0 transition-transform duration-300 group-hover:scale-[1.03]`}
          decoding="async"
          onError={() => setFailed(true)}
        />
        {b.site.headerShowName && (
          <BrandName className={`font-display font-black ${sheet ? 'text-base' : 'text-sm sm:text-lg'} tracking-tight text-white leading-none whitespace-nowrap`} />
        )}
      </>
    );
  }
  return (
    <>
      <BrandMark size="sm" />
      <div className="flex flex-col min-w-0">
        <div className="flex items-center gap-1.5">
          <BrandName className={`font-display font-black ${sheet ? 'text-base' : 'text-sm sm:text-lg'} tracking-tight text-white leading-none whitespace-nowrap`} />
          {!sheet && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse hidden xs:inline-block" title="Agency Available" />}
        </div>
        <span className={`${sheet ? 'text-[10px] font-mono' : 'text-[8px] sm:text-[9px] uppercase tracking-widest font-semibold hidden xs:block'} text-aub-accent-labels mt-0.5`}>
          {sheet ? 'Creative Agency' : 'Creative Studio'}
        </span>
      </div>
    </>
  );
};
