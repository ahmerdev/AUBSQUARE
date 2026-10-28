export type ServiceId = string;

export interface Service {
  id: ServiceId;
  title: string;
  shortDescription: string;
  fullDescription: string;
  iconName: string;
  isPrimary?: boolean;
  deliverables: string[];
  process: { step: string; title: string; description: string }[];
  benefits: string[];
  faqs?: { question: string; answer: string }[];
  slug?: string;
  coverImage?: string;
  coverAlt?: string;
  priceLabel?: string;
  gallery?: string[];
  featured?: boolean;
  ctaLabel?: string;
  ctaUrl?: string;
  relatedProjects?: string[];
  relatedCaseStudies?: string[];
  seo?: SeoBlock;
}

export interface Project {
  id: string;
  slug: string;
  title: string;
  client: string;
  category: string;
  year: string;
  thumbnail: string;
  images: string[];
  summary: string;
  challenge: string;
  solution: string;
  deliverables: string[];
  servicesProvided: string[];
  featured?: boolean;
  metrics?: { label: string; value: string }[];
  testimonial?: {
    quote: string;
    author: string;
    role: string;
  };
  description?: string;
  projectUrl?: string;
  technologies?: string[];
  thumbnailAlt?: string;
  seo?: SeoBlock;
}

export interface CaseStudy {
  id: string;
  slug: string;
  title: string;
  client: string;
  industry: string;
  heroImage: string;
  galleryImages: string[];
  category: string;
  summary: string;
  challenge: string;
  strategy: string;
  solution: string;
  deliverables: string[];
  results: { label: string; value: string; change: string }[];
  featured?: boolean;
  testimonial?: {
    quote: string;
    author: string;
    role: string;
    country: string;
  };
  overview?: string;
  implementation?: string;
  publishDate?: string;
  ctaLabel?: string;
  ctaUrl?: string;
  seo?: SeoBlock;
}

export interface Article {
  id: string;
  slug: string;
  title: string;
  category: 'Branding' | 'Design' | 'Web Development' | 'Marketing' | 'Business';
  excerpt: string;
  featuredImage: string;
  publishDate: string;
  readingTime: string;
  author: {
    name: string;
    role: string;
    avatar: string;
  };
  tableOfContents: { id: string; title: string }[];
  content: {
    sectionId: string;
    heading: string;
    paragraphs: string[];
    pullQuote?: string;
    keyPoints?: string[];
  }[];
  featured?: boolean;
  /** Present when the article comes from the CMS (sanitised HTML). Static fallback articles use `content` instead. */
  contentHtml?: string;
  categorySlug?: string;
  featuredAlt?: string;
  allowComments?: boolean;
  tags?: { name: string; slug: string }[];
  related?: Article[];
  commentsCount?: number;
  seo?: SeoBlock;
}

export interface Comment {
  id: string | number;
  articleSlug?: string;
  authorName: string;
  createdAt: string;
  message: string;
  status?: 'published' | 'pending';
  isStaff?: boolean;
  replies?: Comment[];
}

export interface Testimonial {
  id: string;
  clientName: string;
  role: string;
  company: string;
  country: string;
  avatar: string;
  rating: number;
  content: string;
  projectType: string;
  featured?: boolean;
}

export interface FAQItem {
  id: string;
  question: string;
  answer: string;
  showOnHome?: boolean;
  group?: string;
}

export interface QuoteFormData {
  name: string;
  email: string;
  whatsapp: string;
  countryCode: string;
  service: string;
  budget: string;
  message: string;
}

// ---------------------------------------------------------------- CMS payloads (see backend/apps/api/serializers.py)
export interface SeoBlock {
  title: string;
  description: string;
  canonical?: string;
  ogTitle?: string;
  ogDescription?: string;
  ogImage?: string;
  noindex?: boolean;
  nofollow?: boolean;
}

export interface SiteInfo {
  siteName: string;
  tagline: string;
  logo: string;
  favicon: string;
  /** Fonts chosen in Dashboard → Branding (Google Fonts). `cssUrl` is the ready-made stylesheet link. */
  fonts?: { heading: string; body: string; headingStack: string; bodyStack: string; cssUrl: string };
  /** When false (default) the header shows only the logo, not the company name. */
  headerShowName?: boolean;
  contactEmail: string;
  whatsappNumber: string;
  phone: string;
  address: string;
  businessHours: string;
  socials: Record<string, string>;
  footerText: string;
  copyright: string;
  ctaLabel: string;
  ctaUrl: string;
  cookieNotice: { enabled: boolean; text: string };
  privacyUrl: string;
  termsUrl: string;
  analytics: { gaId: string; gtmId: string; pixelId: string };
  titleSuffix: string;
  defaultSeo: { title: string; description: string; ogImage: string };
}

export interface NavLink { label: string; url: string; newTab: boolean }
export interface BannerInfo { id: number; message: string; linkLabel: string; linkUrl: string; style: string; dismissible: boolean }
export interface HomeSectionData { key: string; label: string; visible: boolean; order: number; fixedFirst: boolean; data: Record<string, any> }

export interface FormConfig {
  budgetOptions: { label: string; value: string }[];
  serviceOptions: string[];
  requirePhone: boolean;
  requireService: boolean;
  requireBudget: boolean;
  placeholders: { name: string; email: string; phone: string; message: string };
  consentRequired: boolean;
  consentText: string;
  marketingOptinEnabled: boolean;
  marketingOptinText: string;
  successTitle: string;
  successMessage: string;
  errorMessage: string;
}

export interface ChatbotConfig {
  enabled: boolean;
  botName: string;
  welcomeMessage: string;
  quickReplies: string[];
  privacyNotice: string;
  aiEnabled: boolean;
  humanHandoff: boolean;
  askContact: boolean;
}

export interface TeamMemberInfo { id: number; name: string; role: string; bio: string; photo: string; photoAlt: string; specialties: string[]; isFounder: boolean; linkedin: string; twitter: string }

export interface Bootstrap {
  site: SiteInfo;
  nav: Record<string, NavLink[]>;
  banner: BannerInfo | null;
  home: HomeSectionData[];
  services: Service[];
  projects: Project[];
  caseStudies: CaseStudy[];
  testimonials: Testimonial[];
  faqs: FAQItem[];
  team: TeamMemberInfo[];
  about: Record<string, any>;
  latestPosts: Article[];
  categories: { name: string; slug: string }[];
  form: FormConfig;
  chatbot: ChatbotConfig;
}
