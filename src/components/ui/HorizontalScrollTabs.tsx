import React, { useRef, useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface TabItem {
  id: string;
  label: string;
  count?: number;
}

interface HorizontalScrollTabsProps {
  tabs: (string | TabItem)[];
  activeTab: string;
  onTabChange: (tabId: string) => void;
  className?: string;
  centerOnDesktop?: boolean;
}

export const HorizontalScrollTabs: React.FC<HorizontalScrollTabsProps> = ({
  tabs,
  activeTab,
  onTabChange,
  className = '',
  centerOnDesktop = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const normalizedTabs: TabItem[] = tabs.map(tab =>
    typeof tab === 'string' ? { id: tab, label: tab } : tab
  );

  const checkScroll = () => {
    if (containerRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = containerRef.current;
      setCanScrollLeft(scrollLeft > 4);
      setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 4);
    }
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, [tabs]);

  // Handle horizontal scrolling via mouse wheel on desktop
  const handleWheel = (e: React.WheelEvent) => {
    if (containerRef.current && (canScrollLeft || canScrollRight)) {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        containerRef.current.scrollLeft += e.deltaY * 0.8;
        checkScroll();
      }
    }
  };

  const scroll = (direction: 'left' | 'right') => {
    if (containerRef.current) {
      const offset = direction === 'left' ? -220 : 220;
      containerRef.current.scrollBy({ left: offset, behavior: 'smooth' });
      setTimeout(checkScroll, 300);
    }
  };

  return (
    <div className={`relative max-w-full group/tabs ${className}`}>
      {/* Left scroll arrow indicator */}
      {canScrollLeft && (
        <button
          onClick={() => scroll('left')}
          className="absolute -left-2 sm:-left-3 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full bg-aub-card/95 border border-aub-border text-white shadow-xl flex items-center justify-center hover:bg-aub-purple hover:scale-110 transition-all backdrop-blur-md"
          aria-label="Scroll tabs left"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      )}

      {/* Left Fade Gradient Mask */}
      {canScrollLeft && (
        <div className="absolute left-0 top-0 bottom-0 w-8 sm:w-12 bg-gradient-to-r from-aub-bg via-aub-bg/80 to-transparent z-10 pointer-events-none rounded-l-full" />
      )}

      {/* Scrollable Container */}
      <div
        ref={containerRef}
        onScroll={checkScroll}
        onWheel={handleWheel}
        className={`flex items-center gap-2 overflow-x-auto no-scrollbar scroll-smooth py-2 px-2 touch-pan-x cursor-grab active:cursor-grabbing ${
          centerOnDesktop ? 'justify-start sm:justify-center' : 'justify-start'
        }`}
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {normalizedTabs.map(tab => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => {
                onTabChange(tab.id);
                // Center clicked tab
                if (containerRef.current) {
                  // subtle micro scroll
                  setTimeout(checkScroll, 100);
                }
              }}
              className={`shrink-0 whitespace-nowrap min-h-[44px] px-4 sm:px-5 py-2 sm:py-2.5 rounded-full text-xs sm:text-sm font-semibold transition-all duration-300 relative select-none ${
                isActive
                  ? 'bg-aub-gradient text-white shadow-glow-magenta scale-[1.02] border border-white/20'
                  : 'bg-aub-card/80 backdrop-blur-md border border-aub-border/80 text-aub-text-secondary hover:text-white hover:border-aub-purple/60 hover:bg-aub-card'
              }`}
            >
              <div className="flex items-center gap-1.5">
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-mono font-bold ${
                      isActive ? 'bg-black/30 text-white' : 'bg-white/10 text-aub-accent-labels'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Right Fade Gradient Mask */}
      {canScrollRight && (
        <div className="absolute right-0 top-0 bottom-0 w-8 sm:w-12 bg-gradient-to-l from-aub-bg via-aub-bg/80 to-transparent z-10 pointer-events-none rounded-r-full" />
      )}

      {/* Right scroll arrow indicator */}
      {canScrollRight && (
        <button
          onClick={() => scroll('right')}
          className="absolute -right-2 sm:-right-3 top-1/2 -translate-y-1/2 z-20 w-9 h-9 rounded-full bg-aub-card/95 border border-aub-border text-white shadow-xl flex items-center justify-center hover:bg-aub-purple hover:scale-110 transition-all backdrop-blur-md"
          aria-label="Scroll tabs right"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
