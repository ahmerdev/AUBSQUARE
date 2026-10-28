import { CaseStudy } from '../types';

export const caseStudiesData: CaseStudy[] = [
  {
    id: 'hotfm-rebrand',
    slug: 'hotfm-105-nationwide-rebrand',
    title: 'Modernizing a National Broadcast Icon for Digital Audiences',
    client: 'HOTFM 105 Network',
    industry: 'Media & Entertainment',
    category: 'Brand Strategy & Visual Identity',
    heroImage: 'https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?auto=format&fit=crop&w=1400&q=85',
    galleryImages: [
      'https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1470225620780-dba8ba36b745?auto=format&fit=crop&w=1200&q=80'
    ],
    summary: 'How AUB SQUARE transformed Pakistan’s premier FM radio network into a multi-platform audio streaming powerhouse.',
    challenge: 'HOTFM 105 had maintained the same broadcast visual identity for over a decade. While their listener base remained loyal, younger demographics were shifting rapidly toward Spotify, podcasts, and digital streams. The existing logo was static, lacked digital legibility at small app icon sizes, and failed to communicate the network\'s high-energy lifestyle programming.',
    strategy: 'We conducted an in-depth demographic analysis comparing traditional FM listenership with digital stream consumption. Our creative direction centered on "Sonic Vibrancy"—translating audio frequencies and youthful energy into an iconic monogram that flexes effortlessly across outdoor mega-billboards, studio mics, and smartphone lock screens.',
    solution: 'Engineered a modern, responsive logo system accompanied by an ultra-vibrant magenta-to-electric-violet color palette. We designed on-air motion bugs, dynamic lower-thirds for video broadcasts, and an ergonomic mobile streaming app design system.',
    deliverables: [
      'Complete Brand Architecture & Guidelines',
      'Dynamic Sonic Logo Mark & Monogram',
      'Digital Streaming Mobile App UI/UX',
      'Nationwide Billboard & Vehicle Fleet Wrap Kit',
      'On-Air Studio Broadcast Motion Graphics'
    ],
    results: [
      { label: 'Brand Recognition', value: '+45%', change: 'Post-launch brand recall study' },
      { label: 'Streaming App Installs', value: '180K+', change: 'First 90 days after relaunch' },
      { label: 'Social Engagement', value: '+62%', change: 'Year-over-year organic reach' }
    ],
    featured: true,
    testimonial: {
      quote: 'AUB SQUARE did not just design a logo; they completely re-energized our entire network. The feedback from both our sponsors and younger listeners has been universally stellar.',
      author: 'Managing Director',
      role: 'HOTFM 105 Media Network',
      country: 'Pakistan'
    }
  },
  {
    id: 'maximum-capital-scale',
    slug: 'maximum-capital-investor-scale',
    title: 'Building Institutional Credibility for an Eight-Figure Private Equity Fund',
    client: 'Maximum Capital Group',
    industry: 'Venture Capital & Private Equity',
    category: 'Corporate Identity & Pitch Strategy',
    heroImage: 'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1400&q=85',
    galleryImages: [
      'https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=1200&q=80'
    ],
    summary: 'A bespoke brand ecosystem, investor prospectus, and web portal that secured $24M in fresh institutional funding.',
    challenge: 'Maximum Capital Group was launching a new opportunistic growth fund targeting mid-market acquisitions in North America and EMEA. In private equity, high-net-worth investors and family offices evaluate firm credibility within seconds. A generic template deck or mediocre website would immediately jeopardize multi-million-dollar commitments.',
    strategy: 'Our team structured a brand positioning of "Disciplined Horizon"—communicating fiduciary rigor, mathematical calculation, and visionary expansion. We chose a refined palette of nocturnal slate, deep royal amethyst, and warm platinum, reflecting understated luxury and enduring stability.',
    solution: 'Designed an architectural monogram evoking growth vectors and vault security. We authored and formatted a comprehensive 48-page investor memorandum with bespoke data visualizations, custom financial charts, and an encrypted LP investor portal interface.',
    deliverables: [
      'Institutional Brand Standards & Identity',
      'Bespoke 48-Page Investor Deck & Keynotes',
      'Private LP Web Portal UI/UX',
      'Executive Stationery with Embossed Foil Printing',
      'Data Room Presentation Templates'
    ],
    results: [
      { label: 'Capital Raised', value: '$24M+', change: 'Fund closed ahead of schedule' },
      { label: 'Deck Conversion Rate', value: '38%', change: 'Meetings converted into LPs' },
      { label: 'Time to Close', value: '-25%', change: 'Reduced LP evaluation timeline' }
    ],
    featured: true,
    testimonial: {
      quote: 'Bilal and Shahwaiz operate at a caliber rarely seen in creative agencies. Their understanding of executive prestige and investor psychology was crucial to closing our fund.',
      author: 'Senior Partner',
      role: 'Maximum Capital Group',
      country: 'United Kingdom / UAE'
    }
  },
  {
    id: 'zitc-cloud-3d',
    slug: 'zitc-interactive-cloud-experience',
    title: 'Transforming Enterprise Cloud Infrastructure into an Interactive 3D Journey',
    client: 'ZITC Cloud Solutions',
    industry: 'Enterprise Cloud & Cybersecurity',
    category: '3D WebGL & Interactive UI/UX',
    heroImage: 'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1400&q=85',
    galleryImages: [
      'https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?auto=format&fit=crop&w=1200&q=80'
    ],
    summary: 'Replacing dry technical documentation with an immersive WebGL digital twin of modern cloud server infrastructure.',
    challenge: 'ZITC had developed cutting-edge distributed microservices and DDoS mitigation infrastructure, but their sales cycle was bogged down by dense whitepapers and static architecture diagrams that failed to captivate enterprise CIOs.',
    strategy: 'Instead of telling prospective clients how fast and resilient ZITC’s servers are, we decided to show them in real-time 3D. We conceptualized an interactive 3D digital server rack that responds to user scroll, allowing visitors to visually "pull out" server nodes and explore latency benchmarks.',
    solution: 'Built an optimized Three.js / React Three Fiber interactive 3D web platform with custom glassmorphism shaders, smooth camera choreography, and real-time enterprise quote calculators.',
    deliverables: [
      'Interactive 3D WebGL Web Platform',
      'Technical Architecture Iconography System',
      'Enterprise RFQ Calculator & Lead Flow',
      'Mobile-Optimized WebGL Fallback Architecture'
    ],
    results: [
      { label: 'Avg Session Duration', value: '4m 12s', change: '+240% vs industry benchmark' },
      { label: 'Inbound Enterprise RFQs', value: '+115%', change: 'Increase in qualified enterprise leads' },
      { label: 'Page Speed Score', value: '98/100', change: 'Optimized WebGL asset streaming' }
    ],
    featured: true,
    testimonial: {
      quote: 'Our enterprise sales demos went from tedious slide presentations to clients literally saying "Wow" within seconds of opening the site. AUB SQUARE delivered pure excellence.',
      author: 'CTO & Co-Founder',
      role: 'ZITC Cloud Solutions',
      country: 'United States'
    }
  }
];
