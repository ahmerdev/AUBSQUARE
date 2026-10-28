import React from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Phone, Mail, MapPin, ArrowUpRight, Heart } from 'lucide-react';
import { useModal } from '../../context/ModalContext';
import { BrandMark, BrandName } from './BrandLogo';
import { isExternal, useNav, useServices, useSite, useTeam, whatsappLink } from '../../context/CmsContext';

const FLink: React.FC<{ to: string; newTab?: boolean; children: React.ReactNode }> = ({ to, newTab, children }) =>
  isExternal(to) ? (
    <a href={to} target={newTab ? '_blank' : undefined} rel="noopener noreferrer" className="hover:text-white transition-colors">{children}</a>
  ) : (
    <Link to={to} className="hover:text-white transition-colors">{children}</Link>
  );

export const Footer: React.FC = () => {
  const { openQuoteModal } = useModal();
  const site = useSite();
  const explore = useNav('footer_explore');
  const extraServices = useNav('footer_services');
  const legal = useNav('footer_legal');
  const services = useServices();
  const founders = useTeam().filter((m) => m.isFounder);
  const wa = whatsappLink(site);
  const socials = Object.entries(site.socials || {});

  return (
    <footer className="relative bg-[#07070D] border-t border-aub-border/80 pt-16 pb-12 overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-aub-magenta/5 rounded-full blur-[140px] pointer-events-none" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-aub-purple/5 rounded-full blur-[140px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 pb-16 border-b border-aub-border/60">
          {/* Col 1: Brand & Bio */}
          <div className="lg:col-span-2 space-y-4">
            <Link to="/" className="flex items-center gap-3 group" aria-label={`${site.siteName || 'AUB SQUARE'} — home`}>
              <BrandMark />
              <BrandName className="font-display font-black text-2xl tracking-tight text-white" />
            </Link>

            <p className="text-aub-text-secondary text-sm leading-relaxed max-w-sm">
              {site.footerText || 'We help startups and small businesses worldwide look like big, trusted brands.'}
            </p>

            {founders.length > 0 && (
              <div className="pt-2 text-xs text-aub-accent-labels space-y-1">
                <p className="font-semibold text-white">Agency Leadership:</p>
                {founders.map((m) => (
                  <p key={m.id}>{m.name} · <span className="text-aub-text-secondary">{m.role}</span></p>
                ))}
              </div>
            )}
          </div>

          {/* Col 2: Navigation */}
          <div>
            <h4 className="text-sm font-bold uppercase tracking-wider text-white mb-4 font-display">
              Explore
            </h4>
            <ul className="space-y-2.5 text-sm text-aub-text-secondary">
              {explore.map((n) => (<li key={n.url + n.label}><FLink to={n.url} newTab={n.newTab}>{n.label}</FLink></li>))}
            </ul>
          </div>

          {/* Col 3: Services */}
          <div>
            <h4 className="text-sm font-bold uppercase tracking-wider text-white mb-4 font-display">
              Services
            </h4>
            <ul className="space-y-2.5 text-sm text-aub-text-secondary">
              {services.map((sv) => (<li key={sv.id}><Link to={`/services/${sv.slug || sv.id}`} className="hover:text-white transition-colors text-left">{sv.title}</Link></li>))}
              {extraServices.map((n) => (<li key={n.url + n.label}><FLink to={n.url} newTab={n.newTab}>{n.label}</FLink></li>))}
            </ul>
          </div>

          {/* Col 4: Contact & Channels */}
          <div>
            <h4 className="text-sm font-bold uppercase tracking-wider text-white mb-4 font-display">
              Connect
            </h4>
            <div className="space-y-3 text-sm text-aub-text-secondary">
              {wa && (
                <a href={wa} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2.5 hover:text-white transition-colors group">
                  <div className="w-8 h-8 rounded-lg bg-[#25D366]/10 border border-[#25D366]/30 flex items-center justify-center text-[#25D366]">
                    <Phone className="w-4 h-4" />
                  </div>
                  <span>{site.phone || 'WhatsApp'}</span>
                </a>
              )}

              {site.contactEmail && (
                <a href={`mailto:${site.contactEmail}`} className="flex items-center gap-2.5 hover:text-white transition-colors group">
                  <div className="w-8 h-8 rounded-lg bg-aub-magenta/10 border border-aub-magenta/30 flex items-center justify-center text-aub-magenta">
                    <Mail className="w-4 h-4" />
                  </div>
                  <span className="break-all">{site.contactEmail}</span>
                </a>
              )}

              {site.address && (
                <div className="flex items-start gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-aub-purple/10 border border-aub-purple/30 flex items-center justify-center text-aub-purple shrink-0">
                    <MapPin className="w-4 h-4" />
                  </div>
                  <span className="whitespace-pre-line">{site.address}</span>
                </div>
              )}

              {socials.length > 0 && (
                <div className="flex flex-wrap items-center gap-2.5 pt-2">
                  {socials.map(([name, url]) => (
                    <a key={name} href={url} target="_blank" rel="noopener noreferrer" className="w-9 h-9 rounded-xl glass-panel flex items-center justify-center text-aub-text-secondary hover:text-white hover:border-aub-purple transition-all" aria-label={name.charAt(0).toUpperCase() + name.slice(1)} title={name.charAt(0).toUpperCase() + name.slice(1)}>
                      <span className="font-bold text-xs">{name.slice(0, 2)}</span>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Bottom Credits & Copyright */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-aub-text-secondary gap-4">
          <p>{site.copyright || `© ${new Date().getFullYear()} ${site.siteName}. All rights reserved.`}</p>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            <Link to="/free-audit" className="hover:text-white transition-colors">Free website audit</Link>
            {legal.map((n) => (<FLink key={n.url + n.label} to={n.url} newTab={n.newTab}>{n.label}</FLink>))}
            <span className="inline-flex items-center gap-1.5 text-aub-accent-labels">
              <span>Made with</span>
              <Heart className="w-3.5 h-3.5 text-aub-magenta fill-aub-magenta" />
              <span>for Global Startups</span>
            </span>
          </div>
        </div>
      </div>
    </footer>
  );
};
