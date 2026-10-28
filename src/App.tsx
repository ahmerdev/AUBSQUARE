import React from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, MotionConfig, motion } from 'framer-motion';
import { ScrollProgress } from './components/ui/ScrollProgress';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { ScrollToTop } from './components/ui/ScrollToTop';
import { QuoteModal } from './components/forms/QuoteModal';
import { AIChatWidget } from './components/widgets/AIChatWidget';
import { GlobalCanvas } from './components/three/GlobalCanvas';
import { SmoothScroll } from './components/ui/SmoothScroll';
import { SiteEffects } from './components/SiteEffects';
import { SiteNotices } from './components/SiteNotices';
import { ServiceDetailPage } from './pages/ServiceDetailPage';

// Pages
import { HomePage } from './pages/HomePage';
import { AboutPage } from './pages/AboutPage';
import { ServicesPage } from './pages/ServicesPage';
import { PortfolioPage } from './pages/PortfolioPage';
import { PortfolioDetailPage } from './pages/PortfolioDetailPage';
import { CaseStudiesPage } from './pages/CaseStudiesPage';
import { CaseStudyDetailPage } from './pages/CaseStudyDetailPage';
import { BlogPage } from './pages/BlogPage';
import { BlogDetailPage } from './pages/BlogDetailPage';
import { ContactPage } from './pages/ContactPage';
import { FreeAuditPage } from './pages/FreeAuditPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  const location = useLocation();
  return (
    <MotionConfig reducedMotion="user">
    <SmoothScroll>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[70] focus:px-4 focus:py-2 focus:rounded-full focus:bg-aub-gradient focus:text-white focus:font-semibold"
      >
        Skip to content
      </a>
      <div className="min-h-screen bg-[#0B0B12] text-white flex flex-col relative selection:bg-aub-magenta selection:text-white">
        {/* Global 3D Interactive WebGL Starfield & Spatial Mesh */}
        <GlobalCanvas />
        <ScrollProgress />

        {/* Scroll restoration */}
        <ScrollToTop />
        <SiteEffects />
        <SiteNotices />

        {/* Persistent Glassmorphism Navigation Header */}
        <Header />

        {/* Main Content View with Routes */}
        <main id="main" className="flex-1 relative z-10">
          {/* Opacity-only page transition: no transform on the page wrapper, so sticky/fixed/measured layouts stay exact. */}
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } }}
              exit={{ opacity: 0, transition: { duration: 0.16 } }}
            >
          <Routes location={location}>
            <Route path="/" element={<HomePage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/services/:slug" element={<ServiceDetailPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/portfolio/:slug" element={<PortfolioDetailPage />} />
            <Route path="/case-studies" element={<CaseStudiesPage />} />
            <Route path="/case-studies/:slug" element={<CaseStudyDetailPage />} />
            <Route path="/blog" element={<BlogPage />} />
            <Route path="/blog/category/:categorySlug" element={<BlogPage />} />
            <Route path="/blog/tag/:tagSlug" element={<BlogPage />} />
            <Route path="/blog/:slug" element={<BlogDetailPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/free-audit" element={<FreeAuditPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
            </motion.div>
          </AnimatePresence>
        </main>

        {/* Global Shared Quote Request Modal */}
        <QuoteModal />

        {/* Floating AI Assistant Widget */}
        <AIChatWidget />

        {/* Persistent Studio Footer */}
        <Footer />
      </div>
    </SmoothScroll>
    </MotionConfig>
  );
};
export default App;
