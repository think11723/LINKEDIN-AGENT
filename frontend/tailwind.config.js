/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        background: '#070B14',
        'bg-soft': '#0B1120',
        'bg-elevated': '#111827',
        'bg-card': '#1A2332',
        surface: 'rgba(17, 24, 39, 0.7)',

        // Borders
        border: 'rgba(255, 255, 255, 0.08)',
        'border-strong': 'rgba(255, 255, 255, 0.14)',
        'border-soft': 'rgba(255, 255, 255, 0.04)',

        // Brand
        'brand-50': '#EAF1FF',
        'brand-100': '#CFE0FF',
        'brand-200': '#A6C4FF',
        'brand-300': '#7BA8FF',
        'brand-400': '#4F8CFF',
        'brand-500': '#3B6FE0',
        'brand-600': '#2C56B8',
        'brand-700': '#1F3F8A',

        // Secondary accent (purple)
        'accent-400': '#9D7DFF',
        'accent-500': '#7C5CFF',
        'accent-600': '#5E45D9',

        // Status
        success: '#22C55E',
        'success-soft': 'rgba(34, 197, 94, 0.14)',
        warning: '#F59E0B',
        'warning-soft': 'rgba(245, 158, 11, 0.14)',
        danger: '#EF4444',
        'danger-soft': 'rgba(239, 68, 68, 0.14)',
        info: '#38BDF8',
        'info-soft': 'rgba(56, 189, 248, 0.14)',

        // Text
        foreground: '#FFFFFF',
        'text-secondary': '#94A3B8',
        'text-muted': '#64748B',
        'text-faint': '#475569',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        display: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        'hero': ['3.25rem', { lineHeight: '1.1', letterSpacing: '-0.025em', fontWeight: '700' }],
        'display': ['2.25rem', { lineHeight: '1.15', letterSpacing: '-0.02em', fontWeight: '700' }],
        'title': ['1.5rem', { lineHeight: '1.25', letterSpacing: '-0.01em', fontWeight: '600' }],
      },
      borderRadius: {
        'xs': '0.375rem',
        sm: '0.5rem',
        DEFAULT: '0.75rem',
        md: '0.875rem',
        lg: '1rem',
        xl: '1.25rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      boxShadow: {
        'panel': '0 1px 0 0 rgba(255,255,255,0.04), 0 12px 32px rgba(0,0,0,0.35)',
        'panel-lg': '0 1px 0 0 rgba(255,255,255,0.04), 0 24px 60px rgba(0,0,0,0.5)',
        'glow-brand': '0 0 28px rgba(79, 140, 255, 0.35)',
        'glow-accent': '0 0 28px rgba(124, 92, 255, 0.35)',
        'inset-soft': 'inset 0 1px 0 0 rgba(255,255,255,0.06)',
      },
      keyframes: {
        'pulse-ring': {
          '0%, 100%': { opacity: 0.6 },
          '50%': { opacity: 1 },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fadeIn': {
          from: { opacity: 0, transform: 'translateY(8px)' },
          to: { opacity: 1, transform: 'translateY(0)' },
        },
        'scaleIn': {
          from: { opacity: 0, transform: 'scale(0.96)' },
          to: { opacity: 1, transform: 'scale(1)' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        'orbit': {
          '0%': { transform: 'rotate(0deg) translateX(40px) rotate(0deg)' },
          '100%': { transform: 'rotate(360deg) translateX(40px) rotate(-360deg)' },
        },
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.4s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'fade-in': 'fadeIn 240ms ease-out both',
        'scale-in': 'scaleIn 180ms ease-out both',
        'gradient-shift': 'gradient-shift 8s ease infinite',
        'float': 'float 6s ease-in-out infinite',
        'orbit': 'orbit 12s linear infinite',
      },
      backdropBlur: {
        xs: '2px',
        '3xl': '64px',
      },
    },
  },
  plugins: [],
};
