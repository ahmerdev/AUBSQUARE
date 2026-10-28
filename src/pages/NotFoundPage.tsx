import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Sparkles, Home, ArrowRight } from 'lucide-react';
import { GlassCard } from '../components/ui/GlassCard';
import { Button } from '../components/ui/Button';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-24 relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute w-96 h-96 bg-aub-magenta/20 blur-[140px] rounded-full pointer-events-none" />
      <div className="absolute w-96 h-96 bg-aub-purple/20 blur-[140px] translate-x-20 rounded-full pointer-events-none" />

      <GlassCard className="max-w-lg w-full text-center p-8 sm:p-12 border-aub-border/80">
        <div className="text-7xl sm:text-8xl font-black text-white font-display text-gradient mb-4">
          404
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white font-display mb-3">
          Page Not Found
        </h1>
        <p className="text-sm text-aub-text-secondary leading-relaxed mb-8">
          The creative canvas you are looking for has been moved, renamed, or never existed in this dimension.
        </p>

        <Link to="/">
          <Button variant="gradient" size="md" leftIcon={<Home className="w-4 h-4" />}>
            Return to Homepage
          </Button>
        </Link>
      </GlassCard>
    </div>
  );
};
