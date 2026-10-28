import React, { useEffect, useRef, useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'framer-motion';
import { Menu, Sparkles, ArrowRight } from 'lucide-react';
import { useModal } from '../../context/ModalContext';
import { MobileBottomSheet } from './MobileBottomSheet';
import { HeaderBrand } from './BrandLogo';
import { isExternal, useNav, useSite } from '../../context/CmsContext';

export const Header: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { openQuoteModal } = useModal();
  const site = useSite();
  const navItems = useNav('header').map((n) => ({ name: n.label, path: n.url, newTab: n.newTab }));
  const location = useLocation();
  const reduce = useReducedMotion();
  const menuButtonRef = useRef<HTMLButtonElement>(null);

  // Magnetic CTA (mouse only)
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 240, damping: 18, mass: 0.45 });
  const sy = useSpring(my, { stiffness: 240, damping: 18, mass: 0.45 });

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20);
    handleScroll();
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Always close the sheet on navigation
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 z-40 transition-[padding] duration-300 flex justify-center px-3 sm:px-6 md:px-8 pointer-events-none pt-[max(0.5rem,env(safe-area-inset-top))] ${
          isScrolled ? 'pb-2 sm:pb-2.5' : 'pb-3 sm:pb-4'
        }`}
      >
        <div
          className={`pointer-events-auto w-full max-w-7xl mx-auto flex items-center justify-between gap-2 rounded-full transition-[background,border-color,box-shadow,padding] duration-300 relative backdrop-blur-2xl ${
            isScrolled
              ? 'bg-[#0B0B12]/90 border border-white/[0.14] py-1.5 pl-3 pr-1.5 sm:pl-5 sm:pr-2 shadow-[0_12px_36px_rgba(0,0,0,0.7),0_0_20px_-3px_rgba(236,0,140,0.22)]'
              : 'bg-[#100C22]/80 border border-aub-border/80 py-2 pl-3 pr-2 sm:pl-6 sm:pr-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.5),0_0_15px_-3px_rgba(123,47,255,0.18)]'
          }`}
        >
          {/* Subtle Top Glowing Hairline */}
          <div className="absolute inset-x-12 top-0 h-[1.5px] bg-gradient-to-r from-transparent via-aub-magenta/70 to-transparent pointer-events-none" />

          {/* Logo */}
          <Link to="/" aria-label={`${site.siteName || 'AUB SQUARE'} — home`} className="flex items-center gap-2.5 sm:gap-3 shrink-0 group py-0.5 min-w-0">
            <HeaderBrand />
          </Link>

          {/* Desktop Navigation */}
          <nav aria-label="Primary" className="hidden lg:flex items-center gap-1 xl:gap-2">
            {navItems.map((item) => isExternal(item.path) ? (
              <a key={item.path} href={item.path} target={item.newTab ? '_blank' : undefined} rel="noopener noreferrer" className="relative px-3.5 py-2 text-xs xl:text-[13px] font-semibold rounded-full whitespace-nowrap text-aub-text-secondary hover:text-white hover:bg-white/[0.06]">{item.name}</a>
            ) : (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  `relative px-3.5 py-2 text-xs xl:text-[13px] font-semibold transition-colors duration-200 rounded-full whitespace-nowrap select-none ${
                    isActive ? 'text-white' : 'text-aub-text-secondary hover:text-white hover:bg-white/[0.06]'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {item.name}
                    {isActive && (
                      <motion.div
                        layoutId="activeNavPill"
                        className="absolute inset-0 rounded-full bg-gradient-to-r from-aub-magenta/20 via-aub-purple/20 to-aub-magenta/20 border border-aub-magenta/60 -z-10 shadow-[0_0_15px_rgba(236,0,140,0.25)] backdrop-blur-sm"
                        transition={{ type: 'spring', bounce: 0.2, duration: 0.45 }}
                      />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Actions: Quote CTA (every breakpoint) + hamburger (< lg) */}
          <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
            <motion.button
              type="button"
              onClick={() => openQuoteModal()}
              aria-label="Get a free quote"
              style={reduce ? undefined : { x: sx, y: sy }}
              onPointerMove={(e) => {
                if (reduce || e.pointerType !== 'mouse') return;
                const r = e.currentTarget.getBoundingClientRect();
                mx.set((e.clientX - r.left - r.width / 2) * 0.18);
                my.set((e.clientY - r.top - r.height / 2) * 0.25);
              }}
              onPointerLeave={() => {
                mx.set(0);
                my.set(0);
              }}
              whileTap={reduce ? undefined : { scale: 0.95 }}
              className="inline-flex items-center justify-center gap-2 h-11 min-w-[44px] px-0 xs:px-4 sm:px-5 rounded-full bg-aub-gradient text-white text-xs sm:text-sm font-bold shadow-[0_0_20px_rgba(236,0,140,0.4)] hover:shadow-[0_0_28px_rgba(123,47,255,0.6)] transition-shadow duration-300 border border-white/20 whitespace-nowrap relative overflow-hidden group"
            >
              <span className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-1000 bg-gradient-to-r from-transparent via-white/25 to-transparent pointer-events-none" />
              <Sparkles className="w-4 h-4 text-white shrink-0" />
              <span className="hidden xs:inline sm:hidden">Quote</span>
              <span className="hidden sm:inline">{site.ctaLabel || 'Get a Free Quote'}</span>
              <ArrowRight className="hidden sm:block w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </motion.button>

            <button
              ref={menuButtonRef}
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="lg:hidden w-11 h-11 rounded-full bg-aub-card/80 border border-aub-border/80 flex items-center justify-center text-white hover:border-aub-magenta transition-colors active:scale-95 shadow-md"
              aria-label="Open navigation menu"
              aria-haspopup="dialog"
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      <MobileBottomSheet isOpen={isMobileMenuOpen} onClose={() => setIsMobileMenuOpen(false)} />
    </>
  );
};
