/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#050508',
        surface: '#0D1B2A',
        card: '#111827',
        border: '#1E3A5F',
        'border-light': '#2D3748',
        primary: '#F59E0B',
        'primary-dark': '#D97706',
        success: '#10B981',
        danger: '#EF4444',
        warning: '#F59E0B',
        info: '#3B82F6',
        muted: '#6B7280',
        'text-primary': '#F9FAFB',
        'text-secondary': '#9CA3AF',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 20px rgba(245, 158, 11, 0.15)',
        'glow-danger': '0 0 20px rgba(239, 68, 68, 0.2)',
        node: '0 4px 24px rgba(0,0,0,0.4)',
      },
    },
  },
  plugins: [],
}
