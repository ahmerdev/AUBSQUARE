import { useSyncExternalStore } from 'react';
import type { SiteInfo } from '../types';

/**
 * Live preview support for Dashboard → Branding.
 * When the site is shown inside the dashboard's preview frame (same origin), the dashboard can post unsaved branding choices
 * (logo, name, header option) and they are shown immediately without saving. Nothing is stored and nothing is sent anywhere.
 */
export type SitePreview = Partial<Pick<SiteInfo, 'logo' | 'siteName' | 'headerShowName'>>;

let current: SitePreview | null = null;
const listeners = new Set<() => void>();

export const setSitePreview = (p: SitePreview | null) => { current = p; listeners.forEach((l) => l()); };
const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };
export const useSitePreview = (): SitePreview | null => useSyncExternalStore(subscribe, () => current, () => null);

/** True only when this page is embedded in a frame (the dashboard preview). */
export const inPreviewFrame = (): boolean => {
  try { return window.self !== window.top; } catch { return true; }
};

const API_ORIGIN = (() => {
  try { const b = (import.meta as any).env?.VITE_API_BASE as string | undefined; return b && /^https?:\/\//.test(b) ? new URL(b).origin : ''; } catch { return ''; }
})();

/** Which dashboard origins may drive the preview: this origin, the API's origin, or a local development address. */
export const trustedParent = (origin: string): boolean =>
  origin === window.location.origin || (!!API_ORIGIN && origin === API_ORIGIN) || /^https?:\/\/(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$/.test(origin);
