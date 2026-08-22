/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Background
        background: '#070709',
        surface: 'rgba(20, 20, 24, 0.72)',
        'surface-2': 'rgba(28, 28, 33, 0.85)',
        'surface-3': 'rgba(255, 255, 255, 0.04)',
        'surface-hover': 'rgba(255, 255, 255, 0.06)',
        // Border
        border: 'rgba(255, 255, 255, 0.08)',
        'border-strong': 'rgba(255, 255, 255, 0.14)',
        'border-subtle': 'rgba(255, 255, 255, 0.05)',
        // Text
        foreground: '#fafafa',
        'text-secondary': '#c2c2c8',
        'text-muted': '#7a7a85',
        'text-faint': '#52525b',
        // Brand — violet accent
        brand: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
          700: '#6d28d9',
          800: '#5b21b6',
          900: '#4c1d95',
        },
        accent: '#8b5cf6',
        'accent-soft': 'rgba(139, 92, 246, 0.16)',
        // Status
        success: '#22c55e',
        'success-soft': 'rgba(34, 197, 94, 0.12)',
        warning: '#f59e0b',
        'warning-soft': 'rgba(245, 158, 11, 0.12)',
        danger: '#f43f5e',
        'danger-soft': 'rgba(244, 63, 94, 0.12)',
        info: '#38bdf8',
        'info-soft': 'rgba(56, 189, 248, 0.12)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      borderRadius: {
        '2xs': '0.25rem',
        xs: '0.375rem',
        sm: '0.5rem',
        DEFAULT: '0.75rem',
        md: '0.875rem',
        lg: '1rem',
        xl: '1.25rem',
        '2xl': '1.5rem',
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.04), 0 12px 32px rgba(0,0,0,0.35)',
        'panel-lg': '0 1px 0 0 rgba(255,255,255,0.04), 0 24px 60px rgba(0,0,0,0.5)',
        'ring-brand': '0 0 0 4px rgba(139, 92, 246, 0.18)',
        'glow-brand': '0 0 28px rgba(139, 92, 246, 0.28)',
      },
      keyframes: {
        pulseRing: {
          '0%, 100%': { opacity: 0.6 },
          '50%': { opacity: 1 },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          from: { opacity: 0, transform: 'translateY(4px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
        scaleIn: {
          from: { opacity: 0, transform: 'scale(0.96)' },
          to: { opacity: 1, transform: 'scale(1)' },
        },
      },
      animation: {
        pulseRing: 'pulseRing 1.4s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
        fadeIn: 'fadeIn 240ms ease-out both',
        scaleIn: 'scaleIn 180ms ease-out both',
      },
    },
  },
  plugins: [],
};
