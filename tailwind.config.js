/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    screens: {
      xs: '480px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1536px',
    },
    extend: {
      fontFamily: {
        display: ['var(--font-heading, Outfit)', 'system-ui', 'sans-serif'],
        sans: ['var(--font-body, "Plus Jakarta Sans")', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
      colors: {
        aub: {
          bg: '#0B0B12',
          'bg-secondary': '#120D24',
          card: '#191430',
          border: '#2E2748',
          magenta: '#EC008C',
          purple: '#7B2FFF',
          violet: '#9333EA',
          'accent-purple': '#C026D3',
          'text-primary': '#FFFFFF',
          'text-secondary': '#B8B3CC',
          'accent-labels': '#C99BFF',
        }
      },
      backgroundImage: {
        'aub-gradient': 'linear-gradient(92deg, #EC008C 10%, #7B2FFF 90%)',
        'aub-gradient-hover': 'linear-gradient(92deg, #FF1493 10%, #9042FF 90%)',
        'radial-glow': 'radial-gradient(circle at 50% 50%, rgba(236, 0, 140, 0.15), rgba(123, 47, 255, 0.1) 40%, transparent 70%)',
      },
      boxShadow: {
        'glow-magenta': '0 0 25px -5px rgba(236, 0, 140, 0.4)',
        'glow-purple': '0 0 25px -5px rgba(123, 47, 255, 0.4)',
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'spin-slow': 'spin 8s linear infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-12px)' },
        }
      }
    },
  },
  plugins: [],
}
