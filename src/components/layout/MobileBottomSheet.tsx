import React, { useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { motion, AnimatePresence, useDragControls, useReducedMotion, Variants } from 'framer-motion';
import { X, Sparkles, Phone, Mail, ArrowRight, Home, Briefcase, FileText, Users, BookOpen, MessageSquare } from 'lucide-react';
import { useModal } from '../../context/ModalContext';
import { useScrollLock } from '../../hooks/useScrollLock';
import { useFocusTrap } from '../../hooks/useFocusTrap';
import { HeaderBrand } from './BrandLogo';
import { isExternal, useNav, useSite, whatsappLink } from '../../context/CmsContext';

interface MobileBottomSheetProps {
  isOpen: boolean;
  onClose: () => void;
}

const navIcons = [
  <Home className="w-4 h-4 text-aub-magenta" />,
  <Sparkles className="w-4 h-4 text-aub-purple" />,
  <Briefcase className="w-4 h-4 text-aub-accent-labels" />,
  <FileText className="w-4 h-4 text-aub-magenta" />,
  <Users className="w-4 h-4 text-aub-purple" />,
  <BookOpen className="w-4 h-4 text-aub-accent-labels" />,
  <MessageSquare className="w-4 h-4 text-aub-magenta" />,
];

const list: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.045, delayChildren: 0.12 } },
};
const item: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } },
};

export const MobileBottomSheet: React.FC<MobileBottomSheetProps> = ({ isOpen, onClose }) => {
  const { openQuoteModal } = useModal();
  const site = useSite();
  const navLinks = useNav('header').map((n, i) => ({ name: n.label, path: n.url, newTab: n.newTab, icon: navIcons[i % navIcons.length] }));
  const wa = whatsappLink(site);
  const sheetRef = useRef<HTMLDivElement>(null);
  const controls = useDragControls();
  const reduce = useReducedMotion();

  useScrollLock(isOpen);
  useFocusTrap(sheetRef, isOpen);

  // Escape closes (only while open)
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  // If the viewport grows past the mobile menu breakpoint while open, close it.
  useEffect(() => {
    if (!isOpen) return;
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = () => mq.matches && onClose();
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Blurred backdrop */}
          <motion.div
            key="sheet-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-md"
            aria-hidden="true"
          />

          {/* Bottom sheet */}
          <motion.div
            key="sheet"
            id="mobile-menu"
            ref={sheetRef}
            tabIndex={-1}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={reduce ? { duration: 0.01 } : { type: 'spring', damping: 30, stiffness: 300, mass: 0.9 }}
            drag="y"
            dragControls={controls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.4 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 90 || info.velocity.y > 600) onClose();
            }}
            className="fixed bottom-0 left-0 right-0 z-50 mx-auto w-full sm:max-w-lg max-h-[min(92dvh,720px)] rounded-t-[28px] sm:rounded-t-[32px] bg-[#100B22]/98 border border-b-0 border-aub-border/90 shadow-[0_-15px_50px_rgba(0,0,0,0.9)] flex flex-col overflow-hidden outline-none"
            role="dialog"
            aria-modal="true"
            aria-label="Site navigation"
          >
            {/* Drag handle + header (the only drag surface, so the list can scroll freely) */}
            <div
              className="shrink-0 px-5 pt-2.5 pb-3 border-b border-aub-border/50 bg-[#120D26]/90 backdrop-blur-md touch-none cursor-grab active:cursor-grabbing"
              onPointerDown={(e) => controls.start(e)}
            >
              <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-aub-border/90" aria-hidden="true" />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <HeaderBrand variant="sheet" />
                </div>

                <button
                  type="button"
                  onClick={onClose}
                  onPointerDown={(e) => e.stopPropagation()}
                  data-autofocus
                  className="w-11 h-11 rounded-full bg-aub-card border border-aub-border flex items-center justify-center text-aub-text-secondary hover:text-white hover:border-aub-magenta/60 transition-colors active:scale-95"
                  aria-label="Close menu"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Links */}
            <div data-lenis-prevent className="flex-1 min-h-0 overflow-y-auto overscroll-contain no-scrollbar px-4 py-3">
              <motion.nav aria-label="Mobile" variants={list} initial={reduce ? 'show' : 'hidden'} animate="show" className="flex flex-col gap-1">
                {navLinks.map((link) => (
                  <motion.div key={link.path} variants={item}>
                    {isExternal(link.path) ? (
                      <a href={link.path} target={link.newTab ? '_blank' : undefined} rel="noopener noreferrer" onClick={onClose} className="flex items-center justify-between min-h-[48px] py-2 px-3.5 rounded-xl text-[15px] font-semibold border border-transparent text-aub-text-secondary hover:text-white hover:bg-white/5">
                        <span className="flex items-center gap-3"><span className="w-8 h-8 rounded-lg bg-aub-card/80 border border-aub-border/60 flex items-center justify-center shrink-0">{link.icon}</span>{link.name}</span>
                        <ArrowRight className="w-4 h-4 text-aub-accent-labels opacity-60" />
                      </a>
                    ) : (
                    <NavLink
                      to={link.path}
                      end={link.path === '/'}
                      onClick={onClose}
                      className={({ isActive }) =>
                        `flex items-center justify-between min-h-[48px] py-2 px-3.5 rounded-xl text-[15px] font-semibold transition-colors ${
                          isActive
                            ? 'bg-aub-card border border-aub-magenta/50 text-white shadow-glow-magenta/20 font-bold'
                            : 'border border-transparent text-aub-text-secondary hover:text-white hover:bg-white/5 active:bg-white/10'
                        }`
                      }
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-aub-card/80 border border-aub-border/60 flex items-center justify-center shrink-0">
                          {link.icon}
                        </div>
                        <span>{link.name}</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-aub-accent-labels opacity-60" />
                    </NavLink>
                    )}
                  </motion.div>
                ))}
              </motion.nav>

              {site.businessHours && (
                <div className="mt-3 p-3 rounded-xl bg-aub-card/40 border border-aub-border/40 flex items-center gap-2 text-[11px] text-aub-text-secondary">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
                  <span>{site.businessHours}</span>
                </div>
              )}
            </div>

            {/* Pinned footer: primary CTA + instant contacts */}
            <div className="shrink-0 px-4 pt-3 border-t border-aub-border/60 bg-[#0E091E] pb-[max(1rem,env(safe-area-inset-bottom))] space-y-2.5">
              <button
                type="button"
                onClick={() => {
                  onClose();
                  setTimeout(() => openQuoteModal(), 120);
                }}
                className="w-full min-h-[52px] rounded-full bg-aub-gradient text-white font-bold text-[15px] shadow-glow-magenta hover:shadow-glow-purple transition-shadow flex items-center justify-center gap-2 active:scale-[0.98]"
              >
                <Sparkles className="w-4 h-4" />
                <span>Get a Free Quote &amp; Proposal</span>
              </button>

              <div className="grid grid-cols-2 gap-2">
                {wa && <a
                  href={wa}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 min-h-[44px] px-3 rounded-xl bg-aub-card border border-aub-border text-xs font-semibold text-white hover:border-[#25D366]/50 transition-colors"
                >
                  <Phone className="w-3.5 h-3.5 text-[#25D366]" />
                  <span>WhatsApp</span>
                </a>}
                {site.contactEmail && <a
                  href={`mailto:${site.contactEmail}`}
                  className="flex items-center justify-center gap-2 min-h-[44px] px-3 rounded-xl bg-aub-card border border-aub-border text-xs font-semibold text-white hover:border-aub-purple/50 transition-colors"
                >
                  <Mail className="w-3.5 h-3.5 text-aub-accent-labels" />
                  <span>Email Agency</span>
                </a>}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
