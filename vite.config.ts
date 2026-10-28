import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    open: true,
    // `npm run dev` + `python manage.py runserver` side by side: the React dev server forwards API and uploaded media to Django.
    proxy: {
      '/api': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true },
      '/media': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // Keep three / R3F / drei OUT of manual chunks: they are only reachable via dynamic import()
        // (lazy 3D scenes), so Rollup emits them as on-demand chunks instead of preloading ~900KB on first paint.
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined;
          if (/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler|@remix-run)\//.test(id)) return 'vendor';
          if (/node_modules\/(framer-motion|motion-dom|motion-utils|canvas-confetti)\//.test(id)) return 'animation';
          return undefined;
        },
      },
    },
  },
});

