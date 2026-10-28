import { Service } from '../types';

export const servicesData: Service[] = [
  {
    id: 'brand-identity',
    title: 'Brand Identity & Logo Design',
    isPrimary: true,
    shortDescription: 'Memorable brand systems, iconic logo marks, comprehensive guidelines, and strategic visual positioning.',
    fullDescription: 'Your brand identity is how the world perceives your business in the first 3 seconds. We engineer cohesive visual languages, memorable logo marks, strategic color palettes, and typographic hierarchies that command respect and convert customers.',
    iconName: 'Sparkles',
    deliverables: [
      'Primary & Secondary Logo Marks',
      'Comprehensive Brand Guidelines (PDF)',
      'Color Palette & Typography System',
      'Business Card & Stationery Kit',
      'Social Media Avatar & Banner Suite',
      'Vector & Print-Ready Files (.AI, .SVG, .PNG, .PDF)'
    ],
    process: [
      { step: '01', title: 'Brand Discovery', description: 'Deep analysis of your target audience, competitors, and unique value proposition.' },
      { step: '02', title: 'Concept Creation', description: 'Exploring 3-4 distinct strategic visual directions and logo concepts.' },
      { step: '03', title: 'Refinement', description: 'Fine-tuning geometry, custom typography, and balanced color systems.' },
      { step: '04', title: 'Brand Kit Delivery', description: 'Exporting production-ready assets and comprehensive usage guidelines.' }
    ],
    benefits: [
      'Instantly look like an established, trustworthy brand',
      'Stand out decisively from commoditized competitors',
      'Unify all customer touchpoints with visual consistency',
      'Accelerate customer acquisition and brand recall'
    ],
    faqs: [
      { question: 'How long does a brand identity project take?', answer: 'Typically 1 to 2 weeks depending on scope and revision cycles.' },
      { question: 'Do I get full vector copyright ownership?', answer: 'Yes! Upon final delivery, 100% intellectual property rights belong to you.' }
    ]
  },
  {
    id: 'graphic-design',
    title: 'Graphic Design',
    isPrimary: false,
    shortDescription: 'High-impact promotional materials, brochures, packaging, pitch decks, and digital assets.',
    fullDescription: 'From high-stakes investor pitch decks to premium packaging and commercial print assets, we craft visuals that arrest attention and clearly communicate your value.',
    iconName: 'Palette',
    deliverables: [
      'Investor Pitch Decks & Keynote Presentations',
      'Brochures, Flyers & Marketing Collateral',
      'Product Packaging & Label Design',
      'Billboards, Rollups & Event Signage',
      'Infographics & Vector Illustrations'
    ],
    process: [
      { step: '01', title: 'Briefing', description: 'Aligning on content hierarchy, dimensions, and audience expectations.' },
      { step: '02', title: 'Visual Composition', description: 'Crafting high-fidelity layouts with intentional white space and focus.' },
      { step: '03', title: 'Feedback Loop', description: 'Rapid revisions and collaborative review.' },
      { step: '04', title: 'Production Export', description: 'Print-ready CMYK/Pantone files with bleed and digital RGB exports.' }
    ],
    benefits: [
      'Communicate complex messages in a glance',
      'Win investor backing with compelling pitch presentations',
      'Elevate product perceived value on shelves and online',
      'Consistent visual language across print and screen'
    ]
  },
  {
    id: 'ui-ux-design',
    title: 'Web & App UI/UX Design',
    isPrimary: false,
    shortDescription: 'User-centric wireframing, high-fidelity prototypes, interactive micro-interactions, and design systems.',
    fullDescription: 'We design intuitive, conversion-optimized web and mobile app interfaces that users love. Grounded in research and modern interaction patterns, our designs turn complex workflows into delightful experiences.',
    iconName: 'Layout',
    deliverables: [
      'User Journey Maps & Wireframes',
      'Figma High-Fidelity UI Mockups',
      'Clickable Interactive Prototypes',
      'Scalable Design System & Component Library',
      'Developer Handoff Specifications & Tokens'
    ],
    process: [
      { step: '01', title: 'User Research', description: 'Mapping user journeys, friction points, and conversion goals.' },
      { step: '02', title: 'Wireframing', description: 'Structuring layout, content priority, and flow before visual styling.' },
      { step: '03', title: 'UI Design', description: 'Applying modern dark/light aesthetics, glassmorphism, and micro-interactions.' },
      { step: '04', title: 'Design System', description: 'Standardizing typography, spacing, and reusable auto-layout components.' }
    ],
    benefits: [
      'Dramatically higher conversion rates and retention',
      'Reduced development time with exact Figma specs',
      'Flawless user flow with zero cognitive overload',
      'Seamless multi-device responsiveness'
    ]
  },
  {
    id: 'web-development',
    title: 'Web Development',
    isPrimary: false,
    shortDescription: 'Modern, high-performance websites built with React, Vite, Next.js, and interactive 3D WebGL experiences.',
    fullDescription: 'We build ultra-fast, animated, production-grade web applications. Combining clean React architectures with smooth animations and interactive 3D elements, our sites engage users and rank high on search engines.',
    iconName: 'Code',
    deliverables: [
      'Custom React / Next.js Web Applications',
      'Interactive 3D WebGL & Three.js Scenes',
      'Framer Motion Micro-Interactions & Scroll Animations',
      'SEO Optimized Semantic Markup & Meta Tags',
      'Responsive Across All Mobile, Tablet & Desktop Viewports',
      'Full Source Code & Deployment Setup'
    ],
    process: [
      { step: '01', title: 'Architecture Planning', description: 'Selecting modular components, data schemas, and state management.' },
      { step: '02', title: 'Development', description: 'Building clean TypeScript React components with Tailwind CSS.' },
      { step: '03', title: '3D & Motion Polish', description: 'Integrating Three.js canvases and responsive Framer Motion animations.' },
      { step: '04', title: 'QA & Optimization', description: 'Performance auditing, cross-browser testing, and SEO verification.' }
    ],
    benefits: [
      'Sub-second load times and exceptional Core Web Vitals',
      'Award-winning visual presentation that wows clients',
      'Clean maintainable codebase built for scalability',
      'Built-in search engine optimization and accessibility'
    ]
  },
  {
    id: 'social-media',
    title: 'Social Media & Content',
    isPrimary: false,
    shortDescription: 'Strategic social templates, carousel designs, motion graphics, and cohesive digital brand presence.',
    fullDescription: 'We help brands capture attention across Instagram, LinkedIn, YouTube, and X. With strategic content design and motion graphics, we turn casual scrollers into engaged followers and loyal buyers.',
    iconName: 'Share2',
    deliverables: [
      'Instagram Grid & Carousel Templates',
      'LinkedIn Thought-Leadership Post Graphics',
      'Motion Graphics & Reel/Short Video Covers',
      'Ad Creatives with High Click-Through Rates',
      'Editable Canva/Figma Template Kits'
    ],
    process: [
      { step: '01', title: 'Audience Strategy', description: 'Identifying visual formats that resonate on target platforms.' },
      { step: '02', title: 'Template Architecture', description: 'Creating distinct post types (educational, promotional, story).' },
      { step: '03', title: 'Content Production', description: 'Crafting striking carousels and motion assets.' },
      { step: '04', title: 'Performance Review', description: 'Iterating designs based on engagement analytics.' }
    ],
    benefits: [
      'Consistent, cohesive daily presence across all platforms',
      'Higher engagement and algorithmic reach',
      'Fast content creation with reusable branded templates',
      'Direct pipeline from social followers to paying clients'
    ]
  }
];
